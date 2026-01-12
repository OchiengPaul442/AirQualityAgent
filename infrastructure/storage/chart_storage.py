"""
Chart Storage Service - Manages chart storage with Cloudinary and local fallback.

Features:
- Primary storage: Cloudinary (cloud-based, scalable, CDN-backed)
- Fallback storage: Local filesystem
- Session-based organization for easy cleanup
- Automatic deletion when sessions are closed
"""

import hashlib
import logging
import os
import time
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    import cloudinary  # type: ignore[import-untyped]

StorageBackend = Literal["cloudinary", "local"]


class ChartStorageService:
    """
    Handles chart storage with Cloudinary as primary and local filesystem as fallback.
    
    Charts are organized by session ID for easy cleanup:
    - Cloudinary: stored in folders like `aeris-aq/charts/{session_id}/chart_{timestamp}_{hash}.png`
    - Local: stored in `charts/{session_id}/chart_{timestamp}_{hash}.png`
    """
    
    def __init__(self):
        """Initialize chart storage with Cloudinary configuration."""
        self.cloudinary_enabled = False
        self.cloudinary: "cloudinary" | None = None  # type: ignore[name-defined]
        self.local_charts_dir = Path("charts")
        self.local_charts_dir.mkdir(exist_ok=True)
        
        # Track charts per session for cleanup
        self.session_charts: dict[str, list[dict[str, Any]]] = {}
        
        # Try to initialize Cloudinary
        try:
            import cloudinary  # type: ignore[import-untyped]
            import cloudinary.api  # type: ignore[import-untyped]
            import cloudinary.uploader  # type: ignore[import-untyped]

            from shared.config.settings import get_settings
            
            settings = get_settings()
            
            # Check if Cloudinary credentials are configured
            cloud_name = getattr(settings, "CLOUDINARY_CLOUD_NAME", "")
            api_key = getattr(settings, "CLOUDINARY_API_KEY", "")
            api_secret = getattr(settings, "CLOUDINARY_API_SECRET", "")
            
            if cloud_name and api_key and api_secret:
                cloudinary.config(
                    cloud_name=cloud_name,
                    api_key=api_key,
                    api_secret=api_secret,
                    secure=True
                )
                self.cloudinary = cloudinary
                self.cloudinary_enabled = True
                logger.info("✓ Cloudinary storage initialized successfully")
            else:
                logger.info("Cloudinary credentials not configured, using local storage only")
                
        except ImportError:
            logger.info("Cloudinary SDK not installed, using local storage only")
        except Exception as e:
            logger.error(f"Failed to initialize Cloudinary: {e}")
            logger.info("Falling back to local storage")
    
    def save_chart(
        self,
        chart_bytes: bytes,
        session_id: str,
        chart_type: str = "chart"
    ) -> dict[str, Any]:
        """
        Save chart to storage (Cloudinary with local fallback).
        
        Args:
            chart_bytes: Chart image as bytes
            session_id: Session ID for organization
            chart_type: Type of chart (for metadata)
            
        Returns:
            dict with:
                - url: Public URL to access the chart
                - backend: Storage backend used ("cloudinary" or "local")
                - path: Local path (if local backend)
                - public_id: Cloudinary public ID (if cloudinary backend)
                - session_id: Session ID for cleanup tracking
        """
        # Generate unique filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        content_hash = hashlib.md5(chart_bytes).hexdigest()[:8]
        filename = f"chart_{timestamp}_{content_hash}.png"
        
        # Try Cloudinary first
        if self.cloudinary_enabled:
            try:
                result = self._save_to_cloudinary(
                    chart_bytes, session_id, filename, chart_type
                )
                self._track_chart(session_id, result)
                return result
            except Exception as e:
                logger.error(f"Cloudinary upload failed: {e}, falling back to local storage")
        
        # Fallback to local storage
        result = self._save_to_local(chart_bytes, session_id, filename)
        self._track_chart(session_id, result)
        return result
    
    def _save_to_cloudinary(
        self,
        chart_bytes: bytes,
        session_id: str,
        filename: str,
        chart_type: str
    ) -> dict[str, Any]:
        """Save chart to Cloudinary."""
        if not self.cloudinary_enabled or self.cloudinary is None:
            raise RuntimeError("Cloudinary not enabled")
            
        # Create organized folder structure: aeris-aq/charts/{session_id}/
        folder = f"aeris-aq/charts/{session_id}"
        # Public ID should just be the filename (folder is handled separately)
        public_id = filename.replace('.png', '')
        
        upload_result = self.cloudinary.uploader.upload(
            chart_bytes,
            public_id=public_id,
            folder=folder,
            resource_type="image",
            format="png",
            tags=[session_id, chart_type, "aeris-aq-chart"],
            context={
                "session_id": session_id,
                "chart_type": chart_type,
                "created_at": datetime.now().isoformat()
            }
        )
        
        logger.info(f"✓ Chart uploaded to Cloudinary: {folder}/{public_id}")
        
        return {
            "url": upload_result["secure_url"],
            "backend": "cloudinary",
            "public_id": f"{folder}/{public_id}",  # Full path for deletion
            "session_id": session_id,
            "filename": filename
        }
    
    def _save_to_local(
        self,
        chart_bytes: bytes,
        session_id: str,
        filename: str
    ) -> dict[str, Any]:
        """Save chart to local filesystem."""
        # Create session-specific directory
        session_dir = self.local_charts_dir / session_id
        session_dir.mkdir(exist_ok=True)
        
        # Save file
        file_path = session_dir / filename
        file_path.write_bytes(chart_bytes)
        
        logger.info(f"✓ Chart saved locally: {file_path}")
        
        # Return URL in format that frontend can access
        # Assuming server serves from /charts/{session_id}/{filename}
        url = f"/charts/{session_id}/{filename}"
        
        return {
            "url": url,
            "backend": "local",
            "path": str(file_path),
            "session_id": session_id,
            "filename": filename
        }
    
    def _track_chart(self, session_id: str, chart_info: dict[str, Any]):
        """Track chart for cleanup when session is deleted."""
        if session_id not in self.session_charts:
            self.session_charts[session_id] = []
        
        self.session_charts[session_id].append({
            **chart_info,
            "created_at": time.time()
        })
    
    def delete_session_charts(self, session_id: str) -> dict[str, Any]:
        """
        Delete all charts for a session.
        
        Args:
            session_id: Session ID to clean up
            
        Returns:
            dict with cleanup statistics
        """
        if session_id not in self.session_charts:
            return {"deleted": 0, "errors": 0, "message": "No charts found for session"}
        
        charts = self.session_charts[session_id]
        deleted_count = 0
        error_count = 0
        
        for chart in charts:
            try:
                if chart["backend"] == "cloudinary":
                    self._delete_from_cloudinary(chart["public_id"])
                else:  # local
                    self._delete_from_local(chart["path"])
                deleted_count += 1
            except Exception as e:
                logger.error(f"Failed to delete chart: {e}")
                error_count += 1
        
        # Remove from tracking
        del self.session_charts[session_id]
        
        logger.info(f"✓ Deleted {deleted_count} charts for session {session_id[:8]}...")
        
        return {
            "deleted": deleted_count,
            "errors": error_count,
            "message": f"Deleted {deleted_count} charts"
        }
    
    def _delete_from_cloudinary(self, public_id: str):
        """Delete chart from Cloudinary."""
        if self.cloudinary_enabled and self.cloudinary is not None:
            try:
                self.cloudinary.uploader.destroy(public_id, resource_type="image")
                logger.debug(f"Deleted from Cloudinary: {public_id}")
            except Exception as e:
                logger.error(f"Failed to delete from Cloudinary {public_id}: {e}")
                raise  # Re-raise to let caller handle it
        else:
            logger.warning(f"Cloudinary not enabled, cannot delete {public_id}")
    
    def _delete_from_local(self, file_path: str):
        """Delete chart from local filesystem."""
        try:
            path = Path(file_path)
            if path.exists():
                path.unlink()
                logger.debug(f"Deleted from local: {file_path}")
                
                # Clean up empty session directory
                session_dir = path.parent
                if session_dir.exists() and not any(session_dir.iterdir()):
                    session_dir.rmdir()
                    logger.debug(f"Removed empty directory: {session_dir}")
            else:
                logger.warning(f"Local file not found for deletion: {file_path}")
        except Exception as e:
            logger.error(f"Failed to delete local file {file_path}: {e}")
            raise  # Re-raise to let caller handle it
    
    def cleanup_old_charts(self, max_age_hours: int = 24):
        """
        Clean up charts older than specified age.
        
        Args:
            max_age_hours: Maximum age in hours before deletion
        """
        cutoff_time = time.time() - (max_age_hours * 3600)
        cleaned_count = 0
        
        for session_id in list(self.session_charts.keys()):
            charts = self.session_charts[session_id]
            expired_charts = [c for c in charts if c.get("created_at", 0) < cutoff_time]
            
            for chart in expired_charts:
                try:
                    if chart["backend"] == "cloudinary":
                        self._delete_from_cloudinary(chart["public_id"])
                    else:
                        self._delete_from_local(chart["path"])
                    cleaned_count += 1
                    charts.remove(chart)
                except Exception as e:
                    logger.error(f"Failed to clean up old chart: {e}")
            
            # Remove session tracking if no charts left
            if not charts:
                del self.session_charts[session_id]
        
        if cleaned_count > 0:
            logger.info(f"✓ Cleaned up {cleaned_count} old charts (>{max_age_hours}h)")
        
        return cleaned_count


# Singleton instance
_storage_service = None


def get_chart_storage_service() -> ChartStorageService:
    """Get or create chart storage service singleton."""
    global _storage_service
    if _storage_service is None:
        _storage_service = ChartStorageService()
    return _storage_service
