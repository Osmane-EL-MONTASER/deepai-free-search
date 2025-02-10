from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_community.llms import Ollama
from fastapi.responses import StreamingResponse
from sqlalchemy import create_engine, Column, Integer, String, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime
from langchain_core.messages import HumanMessage, AIMessage

"""
    -- Create conversations table
    CREATE TABLE CONVERSATION (
        id INT AUTO_INCREMENT PRIMARY KEY,
        topic VARCHAR(100) NOT NULL
    );

    -- Create messages table
    CREATE TABLE MESSAGE (
        id INT AUTO_INCREMENT PRIMARY KEY,
        text VARCHAR(500) NOT NULL,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        conversation_id INT,
        FOREIGN KEY (conversation_id) REFERENCES conversations(id)
    );
"""

Base = declarative_base()

class Conversation(Base):
    __tablename__ = "conversation"
    id = Column(Integer, primary_key=True)
    topic = Column(String(100), nullable=False)

class Message(Base):
    __tablename__ = "message"
    id = Column(Integer, primary_key=True)
    text = Column(String(500), nullable=False)
    is_user = Column(Boolean, nullable=False)
    timestamp = Column(DateTime, default=datetime.now)
    conversation_id = Column(Integer, ForeignKey("conversation.id"))
    
engine = create_engine("sqlite:///roas.db")
Session = sessionmaker(bind=engine)
Base.metadata.create_all(bind=engine)


app = FastAPI(title="LangChain API Server (Ollama)")

# CORS configuration remains the same

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

def initialize_chain():
    prompt = ChatPromptTemplate.from_messages([
        ("system", """You are a helpful assistant. Use conversation history and markdown in responses.
        
        Previous conversation:
        {history}
        
        Current query: {query}"""),
        MessagesPlaceholder(variable_name="history"),
        ("human", "{query}")
    ])
    
    model = Ollama(
        temperature=0.7,
        base_url="http://localhost:11434",
        model="deepseek-r1:14b",
        num_ctx=4096  # Increase context window size
    )
    
    return prompt | model

chain = initialize_chain()

@app.post("/query")
async def query(request: Request):
    data = await request.json()
    session = Session()
    
    try:
        # Check if we're continuing an existing conversation
        conversation_id = data.get('conversation_id')
        if conversation_id:
            conversation = session.query(Conversation).get(conversation_id)
            if not conversation:
                raise HTTPException(status_code=404, detail="Conversation not found")
        else:
            # Create new conversation
            conversation = Conversation(topic=data['query'][:50])
            session.add(conversation)
            session.commit()

        # Save user message
        user_msg = Message(
            text=data['query'],
            is_user=True,
            conversation_id=conversation.id
        )
        session.add(user_msg)
        session.commit()
        
        # Create empty AI message
        ai_msg = Message(
            text='',
            is_user=False,
            conversation_id=conversation.id
        )

        # Get previous messages if continuing conversation
        history_messages = []
        if conversation_id:
            history_messages = session.query(Message).filter(
                Message.conversation_id == conversation_id
            ).order_by(Message.timestamp.asc()).all()

        # Format history for prompt
        history = [
            HumanMessage(content=msg.text) if msg.is_user 
            else AIMessage(content=msg.text)
            for msg in history_messages
        ]

        async def stream_generator():
            full_response = ""
            is_thinking = True

            # Send conversation ID first if new conversation
            if not conversation_id:
                yield f"id: {conversation.id}\n\n"
            
            async for chunk in chain.astream({
                "query": data['query'],
                "history": history
            }):
                if "</think>" in chunk:
                    is_thinking = False
                if not is_thinking:
                    full_response += chunk
                    
                ai_msg.text = full_response
                session.commit()
                yield chunk
            # Final commit after streaming completes
            ai_msg.text = full_response
            session.add(ai_msg)
            session.commit()

        return StreamingResponse(stream_generator(), media_type="text/event-stream")
        
    except Exception as e:
        session.rollback()
        return {"error": str(e)}
    finally:
        session.close()
    
@app.get("/")
async def root():
    return {"message": "Hello World"}

@app.get("/conversations")
async def get_conversations():
    session = Session()
    conversations = session.query(Conversation).order_by(Conversation.id.desc()).all()
    session.close()
    return [{"id": c.id, "topic": c.topic[:50]} for c in conversations]

@app.get("/conversations/{conversation_id}/messages")
async def get_messages(conversation_id: int):
    session = Session()
    messages = session.query(Message).filter(
        Message.conversation_id == conversation_id
    ).order_by(Message.timestamp.asc()).all()
    session.close()
    return [{
        "text": m.text,
        "is_user": m.is_user,
        "is_ai": not m.is_user,
        "is_streaming": False
    } for m in messages] # Donner le type de retour / utiliser pydantic

@app.delete("/conversations/{conversation_id}")
async def delete_conversation(conversation_id: int):
    session = Session()
    try:
        conversation = session.query(Conversation).get(conversation_id)
        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")
        
        # Delete related messages first
        session.query(Message).filter(
            Message.conversation_id == conversation_id
        ).delete()
        
        session.delete(conversation)
        session.commit()
        return {"status": "success"}
    except Exception as e:
        session.rollback()
        return {"error": str(e)}
    finally:
        session.close()

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)