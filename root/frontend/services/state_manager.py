# ABOUTME: Advanced state management service with session persistence, auto-save, and workflow stage tracking.
# ABOUTME: Handles project state, workflow progression, data persistence, and session recovery for the blogging assistant.

import streamlit as st
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Union
from pathlib import Path
import pickle
import hashlib
from enum import Enum

# Import workflow types
from services.workflow_types import WorkflowStage

logger = logging.getLogger(__name__)

class StateManager:
    """Advanced state management for the blogging workflow."""
    
    def __init__(self, auto_save_enabled: bool = True):
        """Initialize state manager with configuration."""
        self.auto_save_enabled = auto_save_enabled
        self.session_key_prefix = "agentic_blog_"
        self.auto_save_file = Path("data/auto_save/session_state.json")
        self.auto_save_interval = timedelta(minutes=5)
        
        # Create auto-save directory if it doesn't exist
        self.auto_save_file.parent.mkdir(parents=True, exist_ok=True)
        
    def initialize(self):
        """Initialize session state with default values and restore previous session if available."""
        # Initialize default state if not already present
        defaults = {
            f'{self.session_key_prefix}current_stage': WorkflowStage.PROJECT_SETUP.value,
            f'{self.session_key_prefix}project_config': None,
            f'{self.session_key_prefix}processing_results': None,
            f'{self.session_key_prefix}outline_data': None,
            f'{self.session_key_prefix}job_id': None,
            f'{self.session_key_prefix}draft_data': None,
            f'{self.session_key_prefix}social_content': None,
            f'{self.session_key_prefix}completed_stages': [],
            f'{self.session_key_prefix}workflow_history': [],
            f'{self.session_key_prefix}last_activity': datetime.now().isoformat(),
            f'{self.session_key_prefix}session_id': self._generate_session_id(),
            f'{self.session_key_prefix}is_initialized': False
        }
        
        # Set defaults for missing keys
        for key, value in defaults.items():
            if key not in st.session_state:
                st.session_state[key] = value
        
        # Try to restore previous session
        if not st.session_state[f'{self.session_key_prefix}is_initialized']:
            self._restore_previous_session()
            st.session_state[f'{self.session_key_prefix}is_initialized'] = True
            
        # Update last activity
        self._update_activity()
    
    def get_current_stage(self) -> WorkflowStage:
        """Get the current workflow stage."""
        stage_value = st.session_state.get(f'{self.session_key_prefix}current_stage', WorkflowStage.PROJECT_SETUP.value)
        try:
            return WorkflowStage(stage_value)
        except ValueError:
            logger.warning(f"Invalid stage value: {stage_value}, defaulting to PROJECT_SETUP")
            return WorkflowStage.PROJECT_SETUP
    
    def advance_to_stage(self, stage: WorkflowStage):
        """Advance workflow to a specific stage."""
        current_stage = self.get_current_stage()
        
        # Mark current stage as completed if advancing
        if current_stage != stage:
            self._mark_stage_completed(current_stage)
            
        # Update current stage
        st.session_state[f'{self.session_key_prefix}current_stage'] = stage.value
        
        # Log workflow progression
        self._log_workflow_event('stage_advance', {
            'from_stage': current_stage.value,
            'to_stage': stage.value,
            'timestamp': datetime.now().isoformat()
        })
        
        # Trigger auto-save
        self._update_activity()
    
    def get_available_stages(self) -> List[WorkflowStage]:
        """Get list of stages that can be navigated to."""
        completed_stages = self._get_completed_stages()
        current_stage = self.get_current_stage()
        
        # Always allow going back to completed stages and current stage
        available = completed_stages + [current_stage]
        
        # Allow advancing to next stage if current stage is complete
        if current_stage in completed_stages:
            next_stage = self._get_next_stage(current_stage)
            if next_stage:
                available.append(next_stage)
        
        # Remove duplicates and sort by stage order
        stages_list = list(WorkflowStage)
        available_unique = []
        for stage in stages_list:
            if stage in available and stage not in available_unique:
                available_unique.append(stage)
                
        return available_unique
    
    def get_project_config(self) -> Optional[Dict[str, Any]]:
        """Get the current project configuration."""
        return st.session_state.get(f'{self.session_key_prefix}project_config')
    
    def set_project_config(self, config: Dict[str, Any]):
        """Set the project configuration."""
        st.session_state[f'{self.session_key_prefix}project_config'] = config
        self._log_workflow_event('project_config_set', config)
        self._update_activity()
    
    def get_processing_results(self) -> Optional[Dict[str, Any]]:
        """Get file processing results."""
        return st.session_state.get(f'{self.session_key_prefix}processing_results')
    
    def set_processing_results(self, results: Dict[str, Any]):
        """Set file processing results."""
        st.session_state[f'{self.session_key_prefix}processing_results'] = results
        self._log_workflow_event('processing_results_set', {
            'file_count': len(results.get('upload_result', {}).get('files', [])),
            'project_id': results.get('project_id')
        })
        self._update_activity()
    
    def get_outline_data(self) -> Optional[Dict[str, Any]]:
        """Get the generated outline data."""
        return st.session_state.get(f'{self.session_key_prefix}outline_data')
    
    def set_outline_data(self, outline: Dict[str, Any]):
        """Set the outline data."""
        st.session_state[f'{self.session_key_prefix}outline_data'] = outline
        self._log_workflow_event('outline_set', {
            'title': outline.get('title', 'Unknown'),
            'sections_count': len(outline.get('sections', []))
        })
        self._update_activity()
    
    def get_job_id(self) -> Optional[str]:
        """Get the current job ID."""
        return st.session_state.get(f'{self.session_key_prefix}job_id')
    
    def set_job_id(self, job_id: str):
        """Set the job ID."""
        st.session_state[f'{self.session_key_prefix}job_id'] = job_id
        self._log_workflow_event('job_id_set', {'job_id': job_id})
        self._update_activity()
    
    def get_draft_data(self) -> Optional[Dict[str, Any]]:
        """Get the blog draft data."""
        return st.session_state.get(f'{self.session_key_prefix}draft_data')
    
    def set_draft_data(self, draft: Dict[str, Any]):
        """Set the blog draft data."""
        st.session_state[f'{self.session_key_prefix}draft_data'] = draft
        
        # Calculate word count for logging
        word_count = 0
        if 'final_draft' in draft:
            word_count = len(draft['final_draft'].split())
            
        self._log_workflow_event('draft_set', {
            'word_count': word_count,
            'has_final_draft': 'final_draft' in draft
        })
        self._update_activity()
    
    def get_social_content(self) -> Optional[Dict[str, Any]]:
        """Get the social media content."""
        return st.session_state.get(f'{self.session_key_prefix}social_content')
    
    def set_social_content(self, content: Dict[str, Any]):
        """Set the social media content."""
        st.session_state[f'{self.session_key_prefix}social_content'] = content
        
        # Log platforms generated
        platforms = [k for k in content.keys() if k in ['twitter', 'linkedin', 'reddit', 'summary']]
        self._log_workflow_event('social_content_set', {
            'platforms': platforms,
            'platform_count': len(platforms)
        })
        self._update_activity()
    
    def resume_project(self, project_data: Dict[str, Any], resume_result: Dict[str, Any]):
        """Resume a project from existing data."""
        # Set project configuration from project data
        project_config = {
            'name': project_data.get('name'),
            'model_name': project_data.get('metadata', {}).get('model_name', 'gemini'),
            'writing_style': project_data.get('metadata', {}).get('writing_style', 'professional'),
            'persona': project_data.get('metadata', {}).get('persona', ''),
            'id': project_data.get('id'),
            'resumed': True,
            'resumed_at': datetime.now().isoformat()
        }
        
        self.set_project_config(project_config)
        
        # Restore state based on resume result
        if resume_result:
            # Restore outline if available
            if 'outline' in resume_result:
                self.set_outline_data(resume_result['outline'])
            
            # Restore job ID if available
            if 'job_id' in resume_result:
                self.set_job_id(resume_result['job_id'])
            
            # Restore draft if available
            if 'final_draft' in resume_result:
                self.set_draft_data(resume_result)
            
            # Restore social content if available
            if 'social_content' in resume_result:
                self.set_social_content(resume_result['social_content'])
        
        # Determine appropriate stage based on available data
        if self.get_social_content():
            self.advance_to_stage(WorkflowStage.EXPORT)
        elif self.get_draft_data():
            self.advance_to_stage(WorkflowStage.BLOG_REFINEMENT)
        elif self.get_outline_data():
            self.advance_to_stage(WorkflowStage.BLOG_DRAFTING)
        else:
            self.advance_to_stage(WorkflowStage.OUTLINE_GENERATION)
        
        self._log_workflow_event('project_resumed', {
            'project_id': project_data.get('id'),
            'project_name': project_data.get('name'),
            'stage': self.get_current_stage().value
        })
    
    def reset_workflow(self):
        """Reset the entire workflow state."""
        # Clear all workflow-related state
        keys_to_clear = [key for key in st.session_state.keys() 
                        if key.startswith(self.session_key_prefix)]
        
        for key in keys_to_clear:
            del st.session_state[key]
        
        # Reinitialize with defaults
        self.initialize()
        
        # Log reset event
        self._log_workflow_event('workflow_reset', {
            'timestamp': datetime.now().isoformat()
        })
    
    def save_state(self):
        """Manually save current state to persistent storage."""
        try:
            state_data = self._get_serializable_state()
            
            with open(self.auto_save_file, 'w') as f:
                json.dump(state_data, f, indent=2)
            
            logger.info("State saved successfully")
            return True
            
        except Exception as e:
            logger.exception(f"Failed to save state: {str(e)}")
            return False
    
    def auto_save(self):
        """Automatically save state if auto-save is enabled and conditions are met."""
        if not self.auto_save_enabled:
            return
        
        try:
            last_activity = datetime.fromisoformat(
                st.session_state.get(f'{self.session_key_prefix}last_activity', datetime.now().isoformat())
            )
            
            # Auto-save if enough time has passed
            if datetime.now() - last_activity > self.auto_save_interval:
                self.save_state()
                
        except Exception as e:
            logger.exception(f"Auto-save failed: {str(e)}")
    
    def get_debug_state(self) -> Dict[str, Any]:
        """Get current state for debugging purposes."""
        return {
            'current_stage': self.get_current_stage().value,
            'completed_stages': [s.value for s in self._get_completed_stages()],
            'has_project_config': self.get_project_config() is not None,
            'has_outline': self.get_outline_data() is not None,
            'has_draft': self.get_draft_data() is not None,
            'has_social_content': self.get_social_content() is not None,
            'job_id': self.get_job_id(),
            'session_id': st.session_state.get(f'{self.session_key_prefix}session_id'),
            'workflow_history_count': len(self._get_workflow_history()),
            'last_activity': st.session_state.get(f'{self.session_key_prefix}last_activity')
        }
    
    def get_workflow_progress(self) -> Dict[str, Any]:
        """Get workflow progress information."""
        completed_stages = self._get_completed_stages()
        total_stages = len(list(WorkflowStage))
        current_stage = self.get_current_stage()
        
        return {
            'current_stage': current_stage.value,
            'completed_count': len(completed_stages),
            'total_count': total_stages,
            'progress_percentage': (len(completed_stages) / total_stages) * 100,
            'next_stage': self._get_next_stage(current_stage),
            'available_stages': [s.value for s in self.get_available_stages()]
        }
    
    # Private helper methods
    
    def _generate_session_id(self) -> str:
        """Generate a unique session ID."""
        timestamp = datetime.now().isoformat()
        return hashlib.md5(timestamp.encode()).hexdigest()[:8]
    
    def _update_activity(self):
        """Update last activity timestamp."""
        st.session_state[f'{self.session_key_prefix}last_activity'] = datetime.now().isoformat()
    
    def _mark_stage_completed(self, stage: WorkflowStage):
        """Mark a workflow stage as completed."""
        completed_stages = self._get_completed_stages()
        if stage not in completed_stages:
            completed_stages.append(stage)
            st.session_state[f'{self.session_key_prefix}completed_stages'] = [s.value for s in completed_stages]
    
    def _get_completed_stages(self) -> List[WorkflowStage]:
        """Get list of completed stages."""
        completed_values = st.session_state.get(f'{self.session_key_prefix}completed_stages', [])
        completed_stages = []
        
        for value in completed_values:
            try:
                stage = WorkflowStage(value)
                completed_stages.append(stage)
            except ValueError:
                logger.warning(f"Invalid completed stage value: {value}")
        
        return completed_stages
    
    def _get_next_stage(self, current_stage: WorkflowStage) -> Optional[WorkflowStage]:
        """Get the next stage in the workflow."""
        stages = list(WorkflowStage)
        try:
            current_index = stages.index(current_stage)
            if current_index < len(stages) - 1:
                return stages[current_index + 1]
        except ValueError:
            pass
        return None
    
    def _log_workflow_event(self, event_type: str, event_data: Dict[str, Any]):
        """Log a workflow event for history tracking."""
        workflow_history = self._get_workflow_history()
        
        event = {
            'type': event_type,
            'data': event_data,
            'timestamp': datetime.now().isoformat(),
            'session_id': st.session_state.get(f'{self.session_key_prefix}session_id')
        }
        
        workflow_history.append(event)
        
        # Keep only last 100 events to prevent memory issues
        if len(workflow_history) > 100:
            workflow_history = workflow_history[-100:]
        
        st.session_state[f'{self.session_key_prefix}workflow_history'] = workflow_history
    
    def _get_workflow_history(self) -> List[Dict[str, Any]]:
        """Get workflow event history."""
        return st.session_state.get(f'{self.session_key_prefix}workflow_history', [])
    
    def _get_serializable_state(self) -> Dict[str, Any]:
        """Get state data that can be serialized to JSON."""
        serializable_state = {}
        
        for key, value in st.session_state.items():
            if key.startswith(self.session_key_prefix):
                # Skip non-serializable values
                try:
                    json.dumps(value)
                    serializable_state[key] = value
                except (TypeError, ValueError):
                    logger.warning(f"Skipping non-serializable state key: {key}")
                    
        return {
            'state': serializable_state,
            'metadata': {
                'saved_at': datetime.now().isoformat(),
                'version': '1.0'
            }
        }
    
    def _restore_previous_session(self):
        """Restore previous session state from auto-save file."""
        try:
            if not self.auto_save_file.exists():
                return
            
            with open(self.auto_save_file, 'r') as f:
                saved_data = json.load(f)
            
            if 'state' in saved_data:
                state_data = saved_data['state']
                
                # Only restore if the saved session is recent (within 24 hours)
                saved_at = saved_data.get('metadata', {}).get('saved_at')
                if saved_at:
                    saved_time = datetime.fromisoformat(saved_at)
                    if datetime.now() - saved_time > timedelta(days=1):
                        logger.info("Saved session is too old, starting fresh")
                        return
                
                # Restore state
                for key, value in state_data.items():
                    if key not in st.session_state:
                        st.session_state[key] = value
                
                logger.info("Previous session restored successfully")
                
        except Exception as e:
            logger.exception(f"Failed to restore previous session: {str(e)}")
    
    def get_project_summary(self) -> Dict[str, Any]:
        """Get a comprehensive summary of the current project."""
        project_config = self.get_project_config()
        outline_data = self.get_outline_data()
        draft_data = self.get_draft_data()
        social_content = self.get_social_content()
        
        summary = {
            'project_name': project_config.get('name') if project_config else 'Unknown',
            'current_stage': self.get_current_stage().value,
            'progress': self.get_workflow_progress(),
            'content_stats': {},
            'timestamps': {}
        }
        
        # Add content statistics
        if draft_data and 'final_draft' in draft_data:
            content = draft_data['final_draft']
            summary['content_stats'] = {
                'word_count': len(content.split()),
                'character_count': len(content),
                'paragraph_count': content.count('\n\n') + 1,
                'estimated_read_time': max(1, len(content.split()) // 200)
            }
        
        # Add outline information
        if outline_data:
            summary['outline_info'] = {
                'title': outline_data.get('title', 'Unknown'),
                'difficulty': outline_data.get('difficulty', 'Unknown'),
                'sections_count': len(outline_data.get('sections', []))
            }
        
        # Add social media information
        if social_content:
            platforms = [k for k in social_content.keys() if k in ['twitter', 'linkedin', 'reddit', 'summary']]
            summary['social_info'] = {
                'platforms_generated': platforms,
                'platform_count': len(platforms)
            }
        
        # Add workflow history summary
        history = self._get_workflow_history()
        if history:
            summary['workflow_info'] = {
                'events_count': len(history),
                'first_event': history[0].get('timestamp') if history else None,
                'last_event': history[-1].get('timestamp') if history else None
            }
        
        return summary
    
    def export_session_data(self) -> Dict[str, Any]:
        """Export all session data for backup or transfer."""
        return {
            'session_export': self._get_serializable_state(),
            'project_summary': self.get_project_summary(),
            'debug_info': self.get_debug_state(),
            'export_metadata': {
                'exported_at': datetime.now().isoformat(),
                'version': '1.0',
                'session_id': st.session_state.get(f'{self.session_key_prefix}session_id')
            }
        }
    
    def import_session_data(self, session_data: Dict[str, Any]) -> bool:
        """Import session data from backup."""
        try:
            if 'session_export' not in session_data:
                raise ValueError("Invalid session data format")
            
            export_data = session_data['session_export']
            if 'state' not in export_data:
                raise ValueError("Missing state data in export")
            
            # Clear current state
            self.reset_workflow()
            
            # Import state
            state_data = export_data['state']
            for key, value in state_data.items():
                st.session_state[key] = value
            
            # Log import event
            self._log_workflow_event('session_imported', {
                'import_timestamp': datetime.now().isoformat(),
                'original_session_id': session_data.get('export_metadata', {}).get('session_id')
            })
            
            logger.info("Session data imported successfully")
            return True
            
        except Exception as e:
            logger.exception(f"Failed to import session data: {str(e)}")
            return False