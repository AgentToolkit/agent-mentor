from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session
from typing import List, Optional
from agent_analytics.server.db.models import LoginEvent, UserAction
from sqlalchemy.sql import func, case
from datetime import datetime
from pydantic import BaseModel
from typing import Optional, Dict, Any

class UserActionRecord(BaseModel):
    timestamp: datetime
    username: str
    action: str
    element: str
    response_time_ms: float
    status_code: int
    success: bool
    error_message: Optional[str]
    payload_size: Optional[int]
    action_metadata: Optional[Dict[str, Any]]
    ip_address: str
    user_agent: str
    
class UsageTracker:
    @staticmethod
    def log_action(
        db: Session,
        username: str,
        action: str,
        element: str,
        response_time_ms: float,
        status_code: int,
        success: bool,
        ip_address: str,
        user_agent: str,
        error_message: str = None,
        payload_size: int = None,
        metadata: dict = None  # Parameter name can stay the same
    ):
        action_event = UserAction(
            username=username,
            action=action,
            element=element,
            response_time_ms=response_time_ms,
            status_code=status_code,
            success=success,
            error_message=error_message,
            payload_size=payload_size,
            action_metadata=metadata,  # Change here to match model
            ip_address=ip_address,
            user_agent=user_agent
        )
        db.add(action_event)
        db.commit()

    @staticmethod
    def get_user_usage(db: Session, username: str, days: int = 30):
        """Get usage statistics for a specific user"""
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        return db.query(UserAction).filter(
            UserAction.username == username,
            UserAction.timestamp >= cutoff
        ).all()

    @staticmethod
    def get_action_stats(db: Session, days: int = 30):
        """Get aggregated statistics for all actions"""
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        
        # Execute the query
        results = db.query(
            UserAction.action,
            func.count().label('total_calls'),
            func.avg(UserAction.response_time_ms).label('avg_response_time'),
            func.sum(case((UserAction.success == True, 1), else_=0)).label('successful_calls'),
            func.avg(UserAction.payload_size).label('avg_payload_size')
        ).filter(
            UserAction.timestamp >= cutoff
        ).group_by(
            UserAction.action
        ).all()
        
        # Convert results to list of dictionaries
        stats = []
        for row in results:
            stats.append({
                'action': row.action,
                'total_calls': int(row.total_calls),  # Convert from SQLAlchemy type
                'avg_response_time': float(row.avg_response_time) if row.avg_response_time else 0,
                'successful_calls': int(row.successful_calls) if row.successful_calls else 0,
                'avg_payload_size': float(row.avg_payload_size) if row.avg_payload_size else 0
            })
        
        return stats
        
    @staticmethod
    def dump_recent_actions(db: Session, days: int = 7):
        """Dump all user actions from the past X days"""
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        
        actions = db.query(UserAction).filter(
            UserAction.timestamp >= cutoff
        ).order_by(
            UserAction.timestamp.desc()
        ).all()
        
        return [
            {
                'timestamp': action.timestamp.isoformat(),
                'username': action.username,
                'action': action.action,
                'element': action.element,
                'response_time_ms': float(action.response_time_ms),
                'status_code': action.status_code,
                'success': action.success,
                'error_message': action.error_message,
                'payload_size': action.payload_size,
                'action_metadata': action.action_metadata,
                'ip_address': action.ip_address,
                'user_agent': action.user_agent
            }
            for action in actions
        ]
        
class LoginTracker:
    @staticmethod
    def log_login(db: Session, username: str, email: Optional[str], full_name: Optional[str], ip_address: Optional[str]):
        """Log a new login event"""
        login_event = LoginEvent(
            username=username,
            email=email,
            full_name=full_name,
            ip_address=ip_address
        )
        db.add(login_event)
        db.commit()
        return login_event

    @staticmethod
    def get_login_history(db: Session, days: int = 7) -> List[LoginEvent]:
        """Get login history for the past X days"""
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
        return db.query(LoginEvent).\
            filter(LoginEvent.timestamp >= cutoff_date).\
            order_by(LoginEvent.timestamp.desc()).\
            all()

    @staticmethod
    def get_user_logins(db: Session, username: str) -> List[LoginEvent]:
        """Get login history for a specific user"""
        return db.query(LoginEvent).\
            filter(LoginEvent.username == username).\
            order_by(LoginEvent.timestamp.desc()).\
            all()