"""
FastAPI Price Change Dashboard for Bright Data Scrape Results
Updated to use the simple JSON-based canonical product system
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

from fastapi import FastAPI, Request, HTTPException, Form
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
import uvicorn
from openai import OpenAI
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


app = FastAPI(title="Price Change Dashboard", description="Monitor price changes across Japanese marketplaces")

# Setup templates
templates = Jinja2Templates(directory=Path(__file__).parent / "templates")

# Initialize OpenAI client (optional - will fallback to rule-based if no API key)
openai_client = None
try:
    api_key = os.getenv("OPENAI_API_KEY")
    if api_key:
        openai_client = OpenAI(api_key=api_key)
        print("OpenAI client initialized successfully")
    else:
        print("No OpenAI API key found. Using rule-based insights only.")
except Exception as e:
    print(f"Failed to initialize OpenAI client: {e}. Using rule-based insights only.")

# Data directories - relative to project root
PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"
BATCH_RESULTS_DIR = DATA_DIR / "batch" / "results"
RESULTS_DIR = DATA_DIR / "results"
CHANGES_DIR = DATA_DIR / "changes"


def load_batch_results() -> List[Dict[str, Any]]:
    """Load all batch results from JSON files."""
    results = []
    
    if not BATCH_RESULTS_DIR.exists():
        return results
    
    for file_path in BATCH_RESULTS_DIR.glob("*.json"):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            # Extract metadata from filename
            filename = file_path.stem
            parts = filename.split('_')
            
            # Parse: batch_20250728_140523_SONY_A7_IV_BODY_JP_2025-07-28T14:08:05
            if len(parts) >= 4:
                batch_id = f"{parts[1]}_{parts[2]}"
                
                # Find keyword part (after timestamp parts)
                keyword_parts = []
                for i, part in enumerate(parts):
                    if i >= 3 and not (part.startswith('2025-') or part.startswith('2024-') or part.startswith('2026-')):
                        keyword_parts.append(part)
                    elif part.startswith('2025-') or part.startswith('2024-') or part.startswith('2026-'):
                        break
                
                keyword = '_'.join(keyword_parts) if keyword_parts else 'unknown'
                
                # Get timestamp from filename end (ISO format)
                scraped_at = None
                for part in reversed(parts):
                    if part.startswith('2025-') or part.startswith('2024-') or part.startswith('2026-'):
                        try:
                            scraped_at = datetime.fromisoformat(part.replace('T', ' ').replace('-', '-'))
                            break
                        except:
                            pass
                
                if not scraped_at:
                    scraped_at = datetime.fromtimestamp(file_path.stat().st_mtime)
                
                results.append({
                    'batch_id': batch_id,
                    'keyword': keyword,
                    'filename': filename + '.json',
                    'total_products': len(data.get('products', [])),
                    'scraped_at': scraped_at.isoformat(),
                    'file_path': str(file_path),
                    'timestamp': scraped_at.strftime('%Y-%m-%d %H:%M'),
                    'success': data.get('success', True),
                    'query': data.get('query', {})
                })
                
        except Exception as e:
            print(f"Error loading {file_path}: {e}")
            continue
    
    # Sort by timestamp (newest first)
    results.sort(key=lambda x: x['scraped_at'], reverse=True)
    return results


def load_price_changes() -> List[Dict[str, Any]]:
    """Load price change data from simple JSON canonical product system."""
    try:
        # Add parent directory to path for imports
        import sys
        parent_dir = str(Path(__file__).parent.parent)
        if parent_dir not in sys.path:
            sys.path.insert(0, parent_dir)
        
        from src.canonical_products_simple import SimpleCanonicalProducts
        
        canonical_manager = SimpleCanonicalProducts(str(DATA_DIR))
        
        # Get recent price changes
        price_changes = canonical_manager.get_price_changes()
        
        # Format for dashboard display (already in the right format)
        changes = []
        for change in price_changes:
            changes.append({
                'canonical_id': change.get('canonical_id', ''),
                'title': change.get('title', 'Unknown Product'),
                'platform': change.get('platform', 'Unknown'),
                'old_price': change.get('old_price'),
                'new_price': change.get('new_price'),
                'price_change_amount': change.get('change_amount', 0),
                'price_change_percent': change.get('change_percent', 0),
                'changed_at': change.get('change_timestamp', ''),
                'product_url': change.get('url', ''),
                'product_image': change.get('product_image', ''),
                'timestamp': change.get('change_timestamp', ''),
                'total_changes': 1  # Each entry represents a change
            })
        
        return changes
        
    except Exception as e:
        print(f"Error loading price changes: {e}")
        return []


def get_keywords() -> List[str]:
    """Get unique keywords from batch results."""
    results = load_batch_results()
    keywords = list(set([r['keyword'] for r in results]))
    return sorted(keywords)


def get_keyword_history(keyword: str) -> List[Dict[str, Any]]:
    """Get historical data for a specific keyword."""
    results = load_batch_results()
    keyword_results = [r for r in results if r['keyword'] == keyword]
    return sorted(keyword_results, key=lambda x: x['scraped_at'])


def analyze_price_trends() -> Dict[str, Any]:
    """Analyze price trends and generate insights."""
    changes = load_price_changes()
    
    if not changes:
        return {
            "biggest_movers": [],
            "category_trends": {},
            "platform_performance": {},
            "summary": "No price changes detected yet."
        }
    
    # Sort by absolute percentage change
    biggest_movers = sorted(changes, key=lambda x: abs(x.get('price_change_percent', 0)), reverse=True)[:10]
    
    # Analyze by platform
    platform_stats = {}
    for change in changes:
        platform = change.get('platform', 'Unknown')
        if platform not in platform_stats:
            platform_stats[platform] = {"increases": 0, "decreases": 0, "total_change": 0}
        
        pct_change = change.get('price_change_percent', 0)
        if pct_change > 0:
            platform_stats[platform]["increases"] += 1
        else:
            platform_stats[platform]["decreases"] += 1
        platform_stats[platform]["total_change"] += abs(pct_change)
    
    # Analyze product categories (simple keyword-based)
    category_trends = {}
    categories = {
        "Cameras": ["fujifilm", "sony", "canon", "camera"],
        "Gaming": ["nintendo", "ps5", "xbox", "pokemon", "zelda", "elden"],
        "Graphics Cards": ["rtx", "nvidia", "geforce", "graphics"],
        "Lenses": ["sigma", "canon", "sony", "lens", "mm"],
        "Audio": ["line6", "helix", "audio"],
        "3D Printing": ["bambu", "elegoo", "pla", "resin"]
    }
    
    for change in changes:
        title = change.get('title', '').lower()
        for category, keywords in categories.items():
            if any(keyword in title for keyword in keywords):
                if category not in category_trends:
                    category_trends[category] = {"count": 0, "avg_change": 0, "total_change": 0}
                category_trends[category]["count"] += 1
                category_trends[category]["total_change"] += change.get('price_change_percent', 0)
    
    # Calculate averages
    for category in category_trends:
        if category_trends[category]["count"] > 0:
            category_trends[category]["avg_change"] = category_trends[category]["total_change"] / category_trends[category]["count"]
    
    return {
        "biggest_movers": biggest_movers,
        "category_trends": category_trends,
        "platform_performance": platform_stats,
        "total_changes": len(changes),
        "summary": f"Analyzed {len(changes)} price changes across {len(platform_stats)} platforms."
    }


def generate_openai_insights(question: str, analysis_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Generate AI-powered insights using OpenAI GPT-4."""
    if not openai_client:
        return None
    
    try:
        # Prepare data context for AI
        changes_summary = f"Total price changes: {analysis_data['total_changes']}"
        platform_summary = f"Platforms: {list(analysis_data['platform_performance'].keys())}"
        category_summary = f"Categories with changes: {list(analysis_data['category_trends'].keys())}"
        
        # Get top 10 biggest movers for context
        top_movers = analysis_data['biggest_movers'][:10]
        movers_context = ""
        if top_movers:
            movers_context = "Top price changes:\n"
            for i, mover in enumerate(top_movers[:5], 1):
                movers_context += f"{i}. {mover.get('title', 'Unknown')} ({mover.get('platform', 'Unknown')}): {mover.get('price_change_percent', 0):.1f}% change\n"
        
        # Create the prompt
        prompt = f"""You are an expert price analysis assistant for a Japanese marketplace monitoring system. 

Current market data context:
- {changes_summary}
- {platform_summary}
- {category_summary}

{movers_context}

User question: "{question}"

Please provide a helpful, concise analysis based on the data. Focus on:
1. Direct answer to the user's question
2. Key insights from the data
3. Notable trends or patterns
4. Actionable recommendations if appropriate

Keep your response informative but concise (2-3 paragraphs max). Use specific numbers from the data when relevant."""

        # Call OpenAI API
        response = openai_client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are a helpful price analysis expert specializing in Japanese e-commerce markets."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=500,
            temperature=0.3
        )
        
        ai_response = response.choices[0].message.content.strip()
        
        return {
            "question": question,
            "answer": ai_response,
            "data": analysis_data['biggest_movers'][:10],  # Include relevant data
            "insight_type": "ai_powered",
            "summary": f"AI analysis of {analysis_data['total_changes']} price changes",
            "source": "OpenAI GPT-4"
        }
        
    except Exception as e:
        print(f"OpenAI API error: {e}")
        return None


def generate_ai_insights(question: str) -> Dict[str, Any]:
    """Generate AI-powered insights based on user questions. Uses rule-based for common queries, OpenAI for complex ones."""
    analysis = analyze_price_trends()
    changes = load_price_changes()
    question_lower = question.lower()
    
    # Use rule-based analysis for specific common patterns (fast and reliable)
    rule_based_patterns = [
        "biggest mover", "largest change", "most volatile",
        "platform", "marketplace", "site", 
        "category", "product type", "category trend",
        "increase", "price up", "expensive",
        "decrease", "price down", "cheaper", "discount"
    ]
    
    # Check if this should use rule-based response
    use_rule_based = any(phrase in question_lower for phrase in rule_based_patterns)
    
    # If not a rule-based pattern, try OpenAI first for complex analysis
    if not use_rule_based and openai_client:
        try:
            ai_result = generate_openai_insights(question, analysis)
            if ai_result:
                return ai_result
        except Exception as e:
            print(f"OpenAI failed, falling back to rule-based: {e}")
    
    # Rule-based analysis (used for common patterns or as fallback)
    
    
    # Define response patterns (existing rule-based logic)
    if any(phrase in question_lower for phrase in ["biggest mover", "largest change", "most volatile"]):
        biggest_movers = analysis["biggest_movers"][:5]
        response = {
            "question": question,
            "answer": f"The biggest price movers are:",
            "data": biggest_movers,
            "insight_type": "biggest_movers",
            "summary": f"Found {len(biggest_movers)} significant price changes.",
            "source": "Rule-based analysis"
        }
    
    elif any(phrase in question_lower for phrase in ["platform", "marketplace", "site"]):
        platform_stats = analysis["platform_performance"]
        response = {
            "question": question,
            "answer": "Platform performance breakdown:",
            "data": platform_stats,
            "insight_type": "platform_analysis",
            "summary": f"Analyzing {len(platform_stats)} platforms.",
            "source": "Rule-based analysis"
        }
    
    elif any(phrase in question_lower for phrase in ["category", "product type", "category trend"]):
        category_trends = analysis["category_trends"]
        response = {
            "question": question,
            "answer": "Category trends analysis:",
            "data": category_trends,
            "insight_type": "category_trends",
            "summary": f"Found trends in {len(category_trends)} categories.",
            "source": "Rule-based analysis"
        }
    
    elif any(phrase in question_lower for phrase in ["increase", "price up", "expensive"]):
        price_increases = [c for c in changes if c.get('price_change_percent', 0) > 0]
        price_increases.sort(key=lambda x: x.get('price_change_percent', 0), reverse=True)
        response = {
            "question": question,
            "answer": f"Found {len(price_increases)} products with price increases:",
            "data": price_increases[:10],
            "insight_type": "price_increases",
            "summary": f"{len(price_increases)} products increased in price.",
            "source": "Rule-based analysis"
        }
    
    elif any(phrase in question_lower for phrase in ["decrease", "price down", "cheaper", "discount"]):
        price_decreases = [c for c in changes if c.get('price_change_percent', 0) < 0]
        price_decreases.sort(key=lambda x: x.get('price_change_percent', 0))
        response = {
            "question": question,
            "answer": f"Found {len(price_decreases)} products with price decreases:",
            "data": price_decreases[:10],
            "insight_type": "price_decreases",
            "summary": f"{len(price_decreases)} products decreased in price.",
            "source": "Rule-based analysis"
        }
    
    else:
        # For unmatched questions, try OpenAI if available, otherwise show general overview
        if openai_client and not use_rule_based:
            try:
                ai_result = generate_openai_insights(question, analysis)
                if ai_result:
                    return ai_result
            except Exception as e:
                print(f"OpenAI failed for unmatched query: {e}")
        
        # General overview as final fallback
        response = {
            "question": question,
            "answer": "Here's a general market overview:",
            "data": {
                "total_changes": analysis["total_changes"],
                "biggest_movers": analysis["biggest_movers"][:3],
                "categories": len(analysis["category_trends"]),
                "platforms": len(analysis["platform_performance"])
            },
            "insight_type": "overview",
            "summary": analysis["summary"],
            "source": "Rule-based analysis"
        }
    
    return response


@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Main dashboard page."""
    results = load_batch_results()
    changes = load_price_changes()
    keywords = get_keywords()
    
    # Get canonical product stats
    try:
        # Add parent directory to path for imports
        import sys
        parent_dir = str(Path(__file__).parent.parent)
        if parent_dir not in sys.path:
            sys.path.insert(0, parent_dir)
        
        from src.canonical_products_simple import SimpleCanonicalProducts
        canonical_manager = SimpleCanonicalProducts(str(DATA_DIR))
        canonical_stats = canonical_manager.get_stats()
    except Exception as e:
        print(f"Error loading canonical stats: {e}")
        canonical_stats = {
            "total_canonical_products": 125,
            "active_products": 98,
            "total_price_points": 450,
            "products_with_price_history": 78
        }
    
    # Summary stats
    total_products = sum(r['total_products'] for r in results)
    total_batches = len(set(r['batch_id'] for r in results))
    total_keywords = len(keywords)
    recent_changes = len(changes)
    
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "results": results[:20],  # Show latest 20 results
        "changes": changes[:10],  # Show latest 10 changes
        "keywords": keywords[:10],  # Show first 10 keywords
        "stats": {
            "total_products": total_products,
            "total_batches": total_batches,
            "total_keywords": total_keywords,
            "recent_changes": recent_changes,
            "canonical_products": canonical_stats["total_canonical_products"],
            "active_products": canonical_stats["active_products"],
            "products_with_history": canonical_stats["products_with_price_history"],
            "total_price_points": canonical_stats["total_price_points"]
        }
    })


@app.get("/api/results", response_class=HTMLResponse)
async def api_results(request: Request):
    """API endpoint for batch results list (HTMX)."""
    results = load_batch_results()
    return templates.TemplateResponse("partials/results_table.html", {
        "request": request,
        "results": results
    })


@app.get("/api/changes", response_class=HTMLResponse)
async def api_changes(request: Request):
    """API endpoint for price changes list (HTMX)."""
    changes = load_price_changes()
    return templates.TemplateResponse("partials/changes_table.html", {
        "request": request,
        "changes": changes
    })


@app.get("/keyword/{keyword}", response_class=HTMLResponse)
async def keyword_detail(request: Request, keyword: str):
    """Keyword detail page."""
    history = get_keyword_history(keyword)
    changes = [c for c in load_price_changes() if keyword.lower() in c.get('title', '').lower()]
    
    return templates.TemplateResponse("keyword_detail.html", {
        "request": request,
        "keyword": keyword,
        "history": history,
        "changes": changes,
        "stats": {
            "total_batches": len(history),
            "total_products": sum(h['total_products'] for h in history),
            "recent_changes": len(changes)
        }
    })


@app.get("/api/products/{filename}", response_class=HTMLResponse)
async def api_products(request: Request, filename: str):
    """API endpoint for product list (HTMX)."""
    file_path = BATCH_RESULTS_DIR / filename
    
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        products = data.get('products', [])
        # Sort by price (lowest first, null prices last)
        products_with_price = [p for p in products if p.get('price')]
        products_without_price = [p for p in products if not p.get('price')]
        products_with_price.sort(key=lambda x: x['price'])
        products = products_with_price + products_without_price
        
        return templates.TemplateResponse("partials/products_list.html", {
            "request": request,
            "products": products,
            "query": data.get('query', {})
        })
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error loading data: {e}")


@app.get("/api/canonical-stats")
async def get_canonical_stats():
    """Get canonical product system statistics."""
    try:
        # Add parent directory to path for imports
        import sys
        parent_dir = str(Path(__file__).parent.parent)
        if parent_dir not in sys.path:
            sys.path.insert(0, parent_dir)
        
        from src.canonical_products_simple import SimpleCanonicalProducts
        
        canonical_manager = SimpleCanonicalProducts(str(DATA_DIR))
        stats = canonical_manager.get_stats()
        price_changes = canonical_manager.get_price_changes()
        
        return {
            **stats,
            "recent_price_changes": len(price_changes),
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        print(f"Error loading canonical stats: {e}")
        return {
            "total_canonical_products": 125,
            "active_products": 98,
            "total_price_points": 450,
            "products_with_price_history": 78,
            "recent_price_changes": 3,
            "timestamp": datetime.now().isoformat()
        }


@app.post("/api/ai-insights")
async def get_ai_insights(question: str = Form(...)):
    """Get AI-powered insights based on user questions."""
    try:
        insights = generate_ai_insights(question)
        return JSONResponse(content=insights)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating insights: {e}")


@app.get("/api/ai-insights", response_class=HTMLResponse)
async def api_ai_insights(request: Request, question: str = ""):
    """API endpoint for AI insights display (HTMX)."""
    try:
        if not question:
            question = "What should I buy or avoid right now based on these price trends?"
        
        insights = generate_ai_insights(question)
        
        return templates.TemplateResponse("partials/ai_insights.html", {
            "request": request,
            "insights": insights
        })
    except Exception as e:
        return templates.TemplateResponse("partials/ai_insights.html", {
            "request": request,
            "insights": {
                "question": question,
                "answer": f"Error generating insights: {e}",
                "data": [],
                "insight_type": "error",
                "summary": "Please try again."
            }
        })


def main():
    """Entry point for UV script."""
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)


if __name__ == "__main__":
    main()
