from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
from pydantic import BaseModel

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
    with sync_playwright() as p:
        # STEALTH MODE: Run invisibly, but disable the automated robot flags
        browser = p.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled"]
        )
        
        # We must fake the User-Agent and Window Size so the firewall thinks we are a real human on a normal PC
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080}
        )
        
        page = context.new_page()
        
        # Delete the webdriver property so the site can't detect the bot
        page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
        try:
            page.goto("https://epds.ap.gov.in/epdsAP/epds", timeout=60000)
            page.wait_for_load_state("domcontentloaded")
            
            try:
                with context.expect_page(timeout=5000) as new_page_info:
                    page.click("a[href*='EpdsDashBoard']")
                page = new_page_info.value 
            except PlaywrightTimeoutError:
                pass 
            
            page.wait_for_load_state("domcontentloaded")
            
            try:
                with context.expect_page(timeout=5000) as new_page_info:
                    page.evaluate("document.getElementById('Ricecard_Search_Screen_latest.epds').click()")
                page = new_page_info.value  
            except PlaywrightTimeoutError:
                pass
            
            page.wait_for_load_state("domcontentloaded")
            
            page.fill("input[id='rice_card_no']", req.rice_card_number, timeout=15000)
            page.click("button:has-text('Submit'), input[type='submit'][value='Submit']")
            
            page.wait_for_selector("table", timeout=20000)
            
            # Add a tiny 2-second invisible pause to allow the table text to fully render in the background
            page.wait_for_timeout(2000)
            
            # 1. SCRAPE GENERAL CARD INFO
            card_info = page.evaluate('''() => {
                let data = { 
                    head_of_family: "N/A", shop_no: "N/A", house_no: "N/A", 
                    colony: "N/A", mandal: "N/A", district: "N/A", secretariat: "N/A" 
                };
                let tds = Array.from(document.querySelectorAll('td, th, span'));
                
                for (let i = 0; i < tds.length; i++) {
                    let text = tds[i].innerText.trim();
                    let nextText = tds[i].nextElementSibling ? tds[i].nextElementSibling.innerText.trim() : "";
                    
                    if (text.includes("Name of Head Of Family")) {
                        data.head_of_family = text.includes(":") ? text.split(":")[1].trim() : nextText;
                    }
                    if (text === "Shop No") data.shop_no = nextText;
                    if (text === "House No") data.house_no = nextText;
                    if (text === "Colony") data.colony = nextText;
                    if (text === "Mandal") data.mandal = nextText;
                    if (text === "District") data.district = nextText;
                    if (text === "Secretariat Name") data.secretariat = nextText;
                }
                return data;
            }''')

            # 2. SCRAPE FULL FAMILY MEMBER DETAILS
            members = []
            rows = page.query_selector_all("table tr")
            
            for row in rows:  
                cols = row.query_selector_all("td")
                
                if len(cols) >= 9:
                    name = cols[0].inner_text().strip()
                    
                    if "Name" in name or name == "":
                        continue
                        
                    members.append({
                        "name": name, 
                        "gender": cols[1].inner_text().strip(),
                        "age": cols[2].inner_text().strip(),
                        "dob": cols[3].inner_text().strip(),
                        "mother": cols[4].inner_text().strip(),
                        "father": cols[5].inner_text().strip(),
                        "spouse": cols[6].inner_text().strip(),
                        "relation": cols[7].inner_text().strip(),
                        "ekyc": cols[8].inner_text().strip()
                    })
            
            browser.close()
            return {
                "status": "success", 
                "card_number": req.rice_card_number, 
                "card_info": card_info,
                "family_members": members
            }
            
        except Exception as e:
            browser.close()
            raise HTTPException(status_code=500, detail=f"Scraping failed internally. Error: {str(e)}")