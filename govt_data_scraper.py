import requests
from bs4 import BeautifulSoup
from typing import List, Dict, Optional
import re

class WeekLinksExtractor:
    """
    Simple extractor to get links for N recent weeks only
    """
    
    def __init__(self):
        self.base_url = "https://idsp.mohfw.gov.in"
        self.weekly_outbreaks_url = f"{self.base_url}/index4.php?lang=1&level=0&linkid=406&lid=3689"
    
    def get_n_weeks_links(self, n: int = 5) -> List[Dict[str, str]]:
        """
        Get links for N most recent weeks
        
        Args:
            n: Number of recent weeks to get links for
            
        Returns:
            List of dictionaries with week info and PDF links
        """
        print(f"🔗 Extracting links for {n} recent weeks...")
        
        try:
            # Fetch the weekly outbreaks page
            response = requests.get(self.weekly_outbreaks_url, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Find all PDF links
            pdf_links = []
            links = soup.find_all('a', href=True)
            
            for link in links:
                href = link.get('href', '')
                text = link.get_text(strip=True)
                
                # Look for PDF links with week patterns
                if 'WriteReadData' in href and href.endswith('.pdf'):
                    # Try to extract week information from text
                    week_info = self._extract_week_info(text, href)
                    if week_info:
                        full_url = href if href.startswith('http') else f"{self.base_url}/{href}"
                        pdf_links.append({
                            'week': week_info['week'],
                            'year': week_info['year'],
                            'title': text,
                            'url': full_url,
                            'filename': href.split('/')[-1] if '/' in href else href
                        })
            
            # Sort by year and week (most recent first)
            pdf_links.sort(key=lambda x: (x['year'], x['week']), reverse=True)
            
            # Return only the first N weeks
            recent_links = pdf_links[:n]
            
            print(f"✅ Found {len(recent_links)} recent week links:")
            for i, link in enumerate(recent_links, 1):
                print(f"   {i}. Week {link['week']}, {link['year']} - {link['filename']}")
            
            return recent_links
            
        except Exception as e:
            print(f"❌ Error fetching week links: {e}")
            return []
    
    def _extract_week_info(self, text: str, href: str) -> Optional[Dict[str, int]]:
        """Extract week and year information from text or URL"""
        
        # Try to extract from text first
        week_patterns = [
            r'week\s*(\d+).*?(\d{4})',
            r'(\d+).*?week.*?(\d{4})',
            r'w(\d+).*?(\d{4})',
            r'(\d{4}).*?week\s*(\d+)',
            r'(\d{4}).*?w(\d+)'
        ]
        
        text_lower = text.lower()
        
        for pattern in week_patterns:
            match = re.search(pattern, text_lower, re.IGNORECASE)
            if match:
                groups = match.groups()
                if len(groups) == 2:
                    # Determine which group is week and which is year
                    num1, num2 = int(groups[0]), int(groups[1])
                    if num1 > 1900 and num2 <= 53:  # num1 is year, num2 is week
                        return {'week': num2, 'year': num1}
                    elif num2 > 1900 and num1 <= 53:  # num2 is year, num1 is week
                        return {'week': num1, 'year': num2}
        
        # Try to extract from URL/filename
        filename = href.split('/')[-1] if '/' in href else href
        
        # Look for patterns in filename like numbers that could be timestamps
        numbers = re.findall(r'\d+', filename)
        
        if numbers:
            # Try to find year and week from numbers
            for num_str in numbers:
                if len(num_str) >= 4:
                    # Could be a timestamp or year
                    year_candidates = [2023, 2024, 2025, 2026]
                    for year in year_candidates:
                        if str(year) in num_str:
                            # Default to current week if we can't determine
                            return {'week': 1, 'year': year}
        
        # Default fallback
        return {'week': 1, 'year': 2025}
    
    def get_links_only(self, n: int = 5) -> List[str]:
        """
        Get just the PDF URLs for N recent weeks
        
        Args:
            n: Number of recent weeks
            
        Returns:
            List of PDF URLs
        """
        week_data = self.get_n_weeks_links(n)
        return [item['url'] for item in week_data]
    
    def get_week_info_dict(self, n: int = 5) -> Dict[str, str]:
        """
        Get week info as a simple dictionary
        
        Args:
            n: Number of recent weeks
            
        Returns:
            Dictionary with week descriptions as keys and URLs as values
        """
        week_data = self.get_n_weeks_links(n)
        return {f"Week {item['week']}, {item['year']}": item['url'] for item in week_data}

# Simple functions for easy use
def get_n_week_links(n: int = 5) -> List[Dict[str, str]]:
    """
    Get N recent week links with full information
    
    Args:
        n: Number of recent weeks to get
        
    Returns:
        List of dictionaries with week, year, title, url, filename
    """
    extractor = WeekLinksExtractor()
    return extractor.get_n_weeks_links(n)

def get_n_week_urls(n: int = 5) -> List[str]:
    """
    Get just the PDF URLs for N recent weeks
    
    Args:
        n: Number of recent weeks to get
        
    Returns:
        List of PDF URLs
    """
    extractor = WeekLinksExtractor()
    return extractor.get_links_only(n)

def get_week_urls_dict(n: int = 5) -> Dict[str, str]:
    """
    Get week URLs as a dictionary
    
    Args:
        n: Number of recent weeks to get
        
    Returns:
        Dictionary with "Week X, YYYY" as keys and URLs as values
    """
    extractor = WeekLinksExtractor()
    return extractor.get_week_info_dict(n)

def display_week_links(links: List[Dict[str, str]]):
    """Display week links in a nice format"""
    print(f"\n📋 {len(links)} Recent Week Links:")
    print("=" * 50)
    
    for i, link in enumerate(links, 1):
        print(f"{i}. Week {link['week']}, {link['year']}")
        print(f"   📄 File: {link['filename']}")
        print(f"   🔗 URL: {link['url']}")
        print(f"   📝 Title: {link['title']}")
        print("-" * 40)


    
    
