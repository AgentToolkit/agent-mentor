from sqlalchemy import Column, Integer, String, DateTime, Float, Boolean, JSON
from sqlalchemy.sql import func
from agent_analytics.server.db.database import Base

class LoginEvent(Base):
    __tablename__ = "login_events"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, index=True)
    email = Column(String)
    full_name = Column(String)
    ip_address = Column(String)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    
class UserAction(Base):
    __tablename__ = "user_actions"
    
    id = Column(Integer, primary_key=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    username = Column(String)
    action = Column(String)  # process, get_traces, get_trace_details
    element = Column(String)  # filename, service_name, trace_id
    response_time_ms = Column(Float)  # Response time in milliseconds
    status_code = Column(Integer)  # HTTP status code
    success = Column(Boolean)  # Whether the action succeeded
    error_message = Column(String, nullable=True)  # Error message if failed
    payload_size = Column(Integer, nullable=True)  # Size of response in bytes
    action_metadata = Column(JSON, nullable=True)  # Additional context as JSON
    ip_address = Column(String)
    user_agent = Column(String)