# Import patch first to fix inspect.getargspec issue
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import patch

from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from phi.agent import Agent
from phi.model.groq import Groq
from phi.tools.yfinance import YFinanceTools
from phi.tools.duckduckgo import DuckDuckGo
import PyPDF2
from typing import List, Optional
import tempfile
from pydantic import BaseModel, validator
import re

# -------------------------
# FastAPI Setup
# -------------------------
app = FastAPI(title="Azka's AI Agent API", version="1.0.0")


from flask import Flask, render_template



from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()   # ❌ Do NOT use Flask(), use FastAPI()

# Add middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # or specify ["http://localhost:3000"] etc
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def root():
    return {"message": "Azka's AI Agent API is running! 🤖"}





app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -------------------------
# PDF Extractor
# -------------------------
def extract_pdf_text(pdf_paths: List[str]) -> str:
    text = ""
    for path in pdf_paths:
        try:
            with open(path, "rb") as f:
                reader = PyPDF2.PdfReader(f)
                for page in reader.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"
        except Exception as e:
            text += f"\n[Error reading {path}: {e}]\n"
    return text

# -------------------------
# Define POS Schemas (Pydantic)
# -------------------------
class Item(BaseModel):
    name: str
    price: float
    quantity: int

    @validator("price")
    def price_must_be_positive(cls, v):
        if v <= 0:
            raise ValueError("Price must be greater than zero")
        return v

    @validator("quantity")
    def quantity_must_be_positive(cls, v):
        if v <= 0:
            raise ValueError("Quantity must be at least 1")
        return v

class Checkout(BaseModel):
    method: str
    total: float

    @validator("method")
    def validate_method(cls, v):
        if v.lower() not in ["upi", "cash", "card"]:
            raise ValueError("Payment method must be one of: upi, cash, card")
        return v.lower()

# -------------------------
# Enhanced Retail POS Agent
# -------------------------
class RetailPOSAgent:
    def __init__(self):
        self.cart: List[Item] = []

    def add_item(self, name: str, price: float, quantity: int) -> str:
        try:
            item = Item(name=name, price=price, quantity=quantity)
            self.cart.append(item)
            total = self.get_total()
            return f"✅ Added {quantity} x {name} (₹{price:.2f}) to cart.\n🛒 Current total: ₹{total:.2f}\n📦 Items in cart: {len(self.cart)}"
        except Exception as e:
            return f"❌ Error adding item: {e}"

    def get_total(self) -> float:
        return sum(i.price * i.quantity for i in self.cart)

    def get_cart_summary(self) -> str:
        if not self.cart:
            return "🛒 Your cart is empty!"
        
        summary = "🛒 **Cart Summary:**\n"
        summary += "```\n"
        for i, item in enumerate(self.cart, 1):
            summary += f"{i}. {item.name} x{item.quantity} @ ₹{item.price:.2f} = ₹{item.price * item.quantity:.2f}\n"
        summary += f"\nTotal: ₹{self.get_total():.2f}\n"
        summary += "```"
        return summary

    def checkout(self, method: str) -> str:
        try:
            if not self.cart:
                return "❌ Cannot checkout: Cart is empty!"
            
            total = self.get_total()
            cart_items = len(self.cart)
            checkout = Checkout(method=method, total=total)
            
            receipt = f"🧾 **RECEIPT**\n"
            receipt += f"{'='*30}\n"
            for i, item in enumerate(self.cart, 1):
                receipt += f"{i}. {item.name} x{item.quantity} @ ₹{item.price:.2f}\n"
            receipt += f"{'='*30}\n"
            receipt += f"💰 **TOTAL: ₹{total:.2f}**\n"
            receipt += f"💳 **Payment: {method.upper()}**\n"
            receipt += f"✅ **Transaction Successful!**\n"
            receipt += f"📦 {cart_items} item(s) purchased\n"
            receipt += f"Thank you for your purchase! 🎉"
            
            self.cart = []  # clear cart after checkout
            return receipt
        except Exception as e:
            return f"❌ Checkout failed: {e}"

    def process_command(self, message: str) -> str:
        message = message.lower().strip()
        
        # Parse add item command with various formats
        add_patterns = [
            r"add\s+(\w+)\s+(\d+(?:\.\d+)?)\s+(\d+)",  # add item price qty
            r"add\s+item[:\s]+(\w+)[,\s]+(?:qty=)?(\d+)[,\s]+(?:price=)?(\d+(?:\.\d+)?)",  # add item: name, qty=2, price=40
        ]
        
        for pattern in add_patterns:
            match = re.search(pattern, message)
            if match:
                if "qty=" in message:  # Second format
                    name, qty, price = match.groups()
                    return self.add_item(name, float(price), int(qty))
                else:  # First format
                    name, price, qty = match.groups()
                    return self.add_item(name, float(price), int(qty))
        
        # Parse checkout command
        checkout_match = re.search(r"checkout\s+(?:with\s+)?(\w+)", message)
        if checkout_match:
            method = checkout_match.group(1)
            return self.checkout(method)
        
        # Handle other commands
        if "total" in message or "cart" in message:
            return self.get_cart_summary()
        
        if "clear" in message or "empty" in message:
            self.cart = []
            return "🗑️ Cart cleared successfully!"
        
        # Help message
        return """🛒 **POS System Commands:**
        
**Add Items:**
• `add <item> <price> <quantity>` - e.g., "add milk 40 2"
• `add item: <name>, qty=<num>, price=<amount>` - e.g., "add item: milk, qty=2, price=40"

**Cart Operations:**
• `total` or `cart` - View cart summary
• `clear` or `empty` - Empty the cart

**Checkout:**
• `checkout <method>` - e.g., "checkout upi", "checkout cash", "checkout card"
• `checkout with <method>` - e.g., "checkout with upi"

Try: "add apple 50 3" or click the quick action buttons! 🎯"""

# Initialize POS agent
pos_agent = RetailPOSAgent()

# -------------------------
# Enhanced Groq Agents
# -------------------------
web_search_agent = Agent(
    name="Web Search Agent",
    role="Search the web for current information and provide detailed responses",
    model=Groq(id="llama-3.1-8b-instant"),
    tools=[DuckDuckGo()],
    instructions=[
        "Always search for the most current and relevant information",
        "If PDFs are provided, extract their text and use it to answer questions",
        "Provide comprehensive answers with sources",
        "Use markdown formatting for better readability",
        "Include relevant links when available"
    ],
    show_tools_calls=True,
    markdown=True,
)

financial_agent = Agent(
    name="Financial Analysis Agent",
    role="Analyze financial data, stock prices, and market trends",
    model=Groq(id="llama-3.1-8b-instant"),
    tools=[YFinanceTools(), DuckDuckGo()],
    instructions=[
        "Use YFinanceTools for accurate financial data",
        "If PDFs contain financial information, extract and analyze it",
        "Provide detailed financial analysis with charts when possible",
        "Include current market data and trends",
        "Use tables for stock data presentation",
        "Always include data sources and timestamps",
        "Explain financial concepts clearly"
    ],
    show_tools_calls=True,
    markdown=True,
)

multimodel_agent = Agent(
    name="MultiModel AI Agent",
    role="Intelligent assistant capable of handling diverse queries using specialized agents",
    model=Groq(id="llama-3.1-8b-instant"),
    team=[web_search_agent, financial_agent],
    instructions=[
        "Analyze the query and delegate to appropriate specialized agents when needed",
        "If PDFs are provided, extract their text and use it to answer questions",
        "Provide comprehensive, well-formatted responses",
        "Use markdown formatting for better readability",
        "Include sources and references",
        "For financial queries, use tables and charts when appropriate",
        "Maintain context across different types of queries"
    ],
    show_tools_calls=True,
    markdown=True,
)

# -------------------------
# Main Chat Endpoint
# -------------------------
@app.post("/chat")
async def chat_with_agent(
    message: str = Form(...),
    agent: str = Form("multimodel"),
    files: List[UploadFile] = File([])
):
    try:
        print(f"Received message: {message}")
        print(f"Selected agent: {agent}")
        print(f"Files uploaded: {len(files)}")
        
        # Handle POS Agent
        if agent == "retail-pos":
            response = pos_agent.process_command(message)
            return {"response": response}

        # Handle PDF files for other agents
        temp_files = []
        pdf_texts = []
        
        for uploaded_file in files:
            if uploaded_file.content_type == "application/pdf":
                try:
                    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
                    content = await uploaded_file.read()
                    temp_file.write(content)
                    temp_file.close()
                    temp_files.append(temp_file.name)
                    print(f"Saved PDF: {uploaded_file.filename}")
                except Exception as e:
                    print(f"Error processing file {uploaded_file.filename}: {e}")

        # Extract PDF text if files were uploaded
        if temp_files:
            try:
                pdf_text = extract_pdf_text(temp_files)
                if pdf_text.strip():
                    pdf_texts.append(f"📄 **Content from uploaded PDF(s):**\n```\n{pdf_text[:2000]}{'...' if len(pdf_text) > 2000 else ''}\n```\n")
                    print(f"Extracted {len(pdf_text)} characters from PDFs")
            except Exception as e:
                print(f"Error extracting PDF text: {e}")

        # Prepare message with PDF content
        if pdf_texts:
            message_with_pdfs = f"{message}\n\n{' '.join(pdf_texts)}"
        else:
            message_with_pdfs = message

        # Select and run the appropriate agent
        agent_map = {
            "multimodel": multimodel_agent,
            "finance": financial_agent,
            "web": web_search_agent
        }
        
        selected_agent = agent_map.get(agent, multimodel_agent)
        print(f"Using agent: {selected_agent.name}")

        # Get response from agent
        response = selected_agent.run(message_with_pdfs, stream=False)
        
        # Clean up temporary files
        for temp_file in temp_files:
            try:
                os.unlink(temp_file)
            except Exception as e:
                print(f"Error cleaning up {temp_file}: {e}")

        return {"response": str(response)}

    except Exception as e:
        print(f"Error in chat endpoint: {e}")
        return {"response": f"⚠️ Sorry, I encountered an error: {str(e)}"}

# -------------------------
# Additional Endpoints
# -------------------------
@app.get("/")
async def root():
    return {
        "message": "Azka's AI Agent API is running! 🤖",
        "version": "1.0.0",
        "agents": ["multimodel", "finance", "web", "retail-pos"],
        "features": ["PDF upload", "Multi-agent support", "POS system"]
    }

@app.get("/agents")
async def get_agents():
    return {
        "agents": {
            "multimodel": {
                "name": "MultiModel AI Agent",
                "description": "Intelligent assistant with access to web search and financial tools",
                "capabilities": ["Web search", "Financial analysis", "PDF processing", "General queries"]
            },
            "finance": {
                "name": "Financial Analysis Agent", 
                "description": "Specialized in financial data analysis and market research",
                "capabilities": ["Stock prices", "Market analysis", "Financial reports", "Economic data"]
            },
            "web": {
                "name": "Web Search Agent",
                "description": "Real-time web search and information retrieval",
                "capabilities": ["Current events", "Research", "Fact checking", "News updates"]
            },
            "retail-pos": {
                "name": "POS System Agent",
                "description": "Point of sale system for retail operations",
                "capabilities": ["Add items", "Calculate totals", "Process payments", "Generate receipts"]
            }
        }
    }

@app.post("/pos/add")
async def add_item_to_pos(
    name: str = Form(...),
    price: float = Form(...),
    quantity: int = Form(1)
):
    """Direct endpoint to add items to POS system"""
    try:
        result = pos_agent.add_item(name, price, quantity)
        return {"success": True, "message": result}
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.get("/pos/cart")
async def get_cart():
    """Get current cart contents"""
    return {
        "cart": [
            {
                "name": item.name,
                "price": item.price,
                "quantity": item.quantity,
                "total": item.price * item.quantity
            }
            for item in pos_agent.cart
        ],
        "total": pos_agent.get_total(),
        "item_count": len(pos_agent.cart)
    }

@app.post("/pos/checkout")
async def checkout_pos(method: str = Form(...)):
    """Process checkout"""
    try:
        result = pos_agent.checkout(method)
        return {"success": True, "receipt": result}
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.delete("/pos/cart")
async def clear_cart():
    """Clear the cart"""
    pos_agent.cart = []
    return {"success": True, "message": "🗑️ Cart cleared successfully!"}

if __name__ == "__main__":
    import uvicorn
    print("🚀 Starting Azka's AI Agent API...")
    print("📊 Available agents: MultiModel, Finance, Web Search, POS System")
    print("🔗 API docs will be available at: http://127.0.0.1:8000/docs")
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)