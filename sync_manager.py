import requests
import time
from threading import Thread, Event
from local_db import LocalDB

class SyncManager:
    """Manages synchronization between local and remote databases"""
    
    def __init__(self, api_url, check_interval=30):
        self.api_url = api_url
        self.check_interval = check_interval
        self.is_online = False
        self.sync_thread = None
        self.stop_event = Event()
        self.auth_token = None
    
    def set_auth_token(self, token):
        """Set JWT token for authenticated requests"""
        self.auth_token = token
    
    def check_connectivity(self):
        """Check if we can reach the remote server"""
        try:
            response = requests.get(
                f"{self.api_url}/health",
                timeout=5
            )
            return response.status_code == 200
        except:
            return False
    
    def start_sync_loop(self):
        """Start background sync thread"""
        if self.sync_thread and self.sync_thread.is_alive():
            return
        
        self.stop_event.clear()
        self.sync_thread = Thread(target=self._sync_loop, daemon=True)
        self.sync_thread.start()
    
    def stop_sync_loop(self):
        """Stop background sync thread"""
        self.stop_event.set()
        if self.sync_thread:
            self.sync_thread.join(timeout=5)
    
    def _sync_loop(self):
        """Background thread that periodically syncs data"""
        while not self.stop_event.is_set():
            was_online = self.is_online
            self.is_online = self.check_connectivity()
            
            # If we just came back online, sync immediately
            if self.is_online and not was_online:
                print("✅ Back online! Starting sync...")
                self.sync_all()
            elif self.is_online:
                # Regular sync when online
                self.sync_all()
            
            # Wait before next check
            self.stop_event.wait(self.check_interval)
    
    def sync_all(self):
        """Sync all unsynced notes with the server"""
        if not self.is_online or not self.auth_token:
            return
        
        try:
            user_id = self._get_user_id_from_token()
            unsynced_notes = LocalDB.get_unsynced_notes(user_id)
            
            headers = {'Authorization': f'Bearer {self.auth_token}'}
            
            for note in unsynced_notes:
                try:
                    # Try to sync this note
                    if note['id'] > 0:  # Existing note
                        response = requests.put(
                            f"{self.api_url}/notes/{note['id']}",
                            json=note,
                            headers=headers,
                            timeout=10
                        )
                    else:  # New note
                        response = requests.post(
                            f"{self.api_url}/notes",
                            json=note,
                            headers=headers,
                            timeout=10
                        )
                    
                    if response.status_code == 200:
                        # Successfully synced
                        LocalDB.mark_synced(note['id'])
                    elif response.status_code == 409:
                        # Conflict detected
                        self._handle_conflict(note, response.json())
                
                except requests.RequestException as e:
                    print(f"❌ Failed to sync note {note['id']}: {str(e)}")
                    continue
            
            # Pull any new notes from server
            self._pull_from_server(user_id, headers)
        
        except Exception as e:
            print(f"❌ Sync failed: {str(e)}")
    
    def _handle_conflict(self, local_note, server_response):
        """Handle sync conflicts between local and server notes"""
        server_note = server_response.get('note')
        
        # Compare versions
        if local_note['version'] > server_note['version']:
            # Local is newer
            self._force_push(local_note)
        elif local_note['version'] < server_note['version']:
            # Server is newer
            self._accept_server_version(server_note)
        else:
            # Create conflict copy
            self._create_conflict_copy(local_note, server_note)
    
    def _create_conflict_copy(self, local_note, server_note):
        """Create a copy of the local note to preserve both versions"""
        conflict_note = local_note.copy()
        conflict_note['title'] = f"{local_note['title']} (Conflict Copy)"
        conflict_note['id'] = None
        LocalDB.create_note(
            user_id=local_note['user_id'],
            title=conflict_note['title'],
            content=conflict_note['content'],
            tags=conflict_note.get('tags', [])
        )
        self._accept_server_version(server_note)
    
    def _pull_from_server(self, user_id, headers):
        """Pull any new notes from server that are missing locally"""
        try:
            response = requests.get(
                f"{self.api_url}/notes",
                headers=headers,
                timeout=10
            )
            
            if response.status_code == 200:
                server_notes = response.json()
                local_notes = LocalDB.get_notes(user_id)
                local_ids = {note['id'] for note in local_notes}
                
                for server_note in server_notes:
                    if server_note['id'] not in local_ids:
                        LocalDB.create_note(
                            user_id=user_id,
                            title=server_note['title'],
                            content=server_note['content'],
                            tags=server_note.get('tags', [])
                        )
        except Exception as e:
            print(f"❌ Failed to pull from server: {str(e)}")
    
    def _get_user_id_from_token(self):
        """Extract user ID from JWT token (mock version)"""
        return 1  # Just a placeholder
    
    def _force_push(self, note):
        """Force push local version to server"""
        pass
    
    def _accept_server_version(self, server_note):
        """Accept server version and update local"""
        pass
