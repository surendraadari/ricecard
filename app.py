from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import requests
from bs4 import BeautifulSoup

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

class CardRequest(BaseModel):
    rice_card_number: str

@app.get("/", response_class=HTMLResponse)
def serve_frontend():
    try:
        with open("index.html", "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return "<h1>index.html not found.</h1>"

@app.post("/api/fetch-rice-card")
def fetch_rice_card(req: CardRequest):
    session = requests.Session()
    
    # CORRECTED GOVERNMENT PORTAL DOMAIN PATHWAY (epdsap.ap.gov.in)
    search_url = "https://epdsap.ap.gov.in/epdsAP/epds/Ricecard_Search_Screen_latest.epds"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:152.0) Gecko/20100101 Firefox/152.0",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Content-Type": "application/x-www-form-urlencoded",
        "Origin": "https://epdsap.ap.gov.in",
        "Referer": "https://epdsap.ap.gov.in/epdsAP/epds/publicepdsDashBoard.epds"
    }

    try:
        # Recreating the exact network payload profile captured from your inspector pane
        payload = {
            "csrfPreventionSalt": "",
            "rice_card_no": req.rice_card_number
        }
        
        # Fire structural post stream directly to the corrected server context
        response = session.post(search_url, data=payload, headers=headers, timeout=25)
        
        if response.status_code != 200:
            raise HTTPException(status_code=500, detail=f"Target portal rejected connection stream: {response.status_code}")
            
        soup = BeautifulSoup(response.text, 'html.parser')
        
        card_info = {
            "head_of_family": "N/A", "shop_no": "N/A", "house_no": "N/A",
            "colony": "N/A", "mandal": "N/A", "district": "N/A", "secretariat": "N/A"
        }
        
        # Process structural profile details text arrays
        tds = soup.find_all(['td', 'th', 'span'])
        for i, td in enumerate(tds):
            text = td.get_text().strip()
            next_text = tds[i+1].get_text().strip() if i+1 < len(tds) else ""
            
            if "Name of Head Of Family" in text:
                card_info["head_of_family"] = text.split(":")[-1].strip() if ":" in text else next_text
            if "Shop No" in text: card_info["shop_no"] = next_text
            if "House No" in text: card_info["house_no"] = next_text
            if "Colony" in text: card_info["colony"] = next_text
            if "Mandal" in text: card_info["mandal"] = next_text
            if "District" in text: card_info["district"] = next_text
            if "Secretariat Name" in text: card_info["secretariat"] = next_text

        # Process core household layout grids
        members = []
        rows = soup.find_all('tr')
        
        for row in rows:
            cols = row.find_all('td')
            if len(cols) >= 5:
                name = cols[0].get_text().strip()
                if "Name" in name or name == "" or name.isdigit():
                    continue
                members.append({
                    "name": name,
                    "gender": cols[1].get_text().strip() if len(cols) > 1 else "N/A",
                    "age": cols[2].get_text().strip() if len(cols) > 2 else "N/A",
                    "dob": cols[3].get_text().strip() if len(cols) > 3 else "N/A",
                    "relation": cols[4].get_text().strip() if len(cols) > 4 else "N/A"
                })
                
        if not members:
            return {"status": "error", "message": "No active database registration members discovered for this index."}

        return {
            "status": "success",
            "card_number": req.rice_card_number,
            "card_info": card_info,
            "family_members": members
        }

    except Exception as e:
        import traceback
        print("--- EPDSAP CONNECTION TRACEBACK ---")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Backend routing engine failure: {str(e)}")
