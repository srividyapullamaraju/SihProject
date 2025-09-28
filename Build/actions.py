from typing import Any, Text, Dict, List
import google.generativeai as genai
import os
import re
import base64
import requests
from PIL import Image
from io import BytesIO
from dotenv import load_dotenv
from bs4 import BeautifulSoup

from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher

# Load environment variables
load_dotenv()

class ActionHealthAdviceMultilingual(Action):
    
    def name(self) -> Text:
        return "action_health_advice_multilingual"
    
    def detect_language(self, text: str) -> str:
        """Detect the language of input text using Gemini"""
        try:
            genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
            model = genai.GenerativeModel('gemini-1.5-flash')
            
            detection_prompt = f"""
            Detect the language of this text and respond with ONLY the language code:
            - en (English)
            - hi (Hindi) 
            - te (Telugu)
            
            Text: "{text}"
            
            Respond with only the language code (e.g., "hi", "en", "te").
            """
            
            response = model.generate_content(detection_prompt)
            detected_lang = response.text.strip().lower()
            
            # Validate the detected language
            valid_langs = ['en', 'hi', 'te']
            return detected_lang if detected_lang in valid_langs else 'en'
            
        except Exception as e:
            print(f"Language detection error: {e}")
            return 'en'  # Default to English
    
    def get_language_name(self, lang_code: str) -> str:
        """Get full language name from code"""
        lang_map = {
            'en': 'English',
            'hi': 'Hindi', 
            'te': 'Telugu'
        }
        return lang_map.get(lang_code, 'English')
    
    def process_image_from_url(self, image_url: str):
        """Download and process image from URL for Gemini"""
        try:
            response = requests.get(image_url)
            response.raise_for_status()
            
            # Open image with PIL
            image = Image.open(BytesIO(response.content))
            
            # Convert to RGB if necessary
            if image.mode != 'RGB':
                image = image.convert('RGB')
            
            return image
        except Exception as e:
            print(f"Error processing image: {e}")
            return None
    
    def extract_image_from_message(self, tracker: Tracker):
        """Extract image data from WhatsApp message"""
        try:
            # Get the latest message
            latest_message = tracker.latest_message
            
            # Check for attachments or media in the message
            if 'attachments' in latest_message:
                attachments = latest_message['attachments']
                for attachment in attachments:
                    if attachment.get('type') == 'image':
                        image_url = attachment.get('payload', {}).get('url')
                        if image_url:
                            return self.process_image_from_url(image_url)
            
            # Check for metadata that might contain image information
            metadata = latest_message.get('metadata', {})
            if 'image_url' in metadata:
                return self.process_image_from_url(metadata['image_url'])
            
            return None
        except Exception as e:
            print(f"Error extracting image: {e}")
            return None
    
    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        
        # Configure Gemini API
        genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
        model = genai.GenerativeModel('gemini-2.5-flash')
        
        # Get user's latest message
        user_message = tracker.latest_message.get('text', '')
        
        # Extract image if present
        image = self.extract_image_from_message(tracker)
        
        # Detect language from text (if available)
        if user_message:
            detected_lang = self.detect_language(user_message)
        else:
            detected_lang = 'en'  # Default to English if no text
        
        lang_name = self.get_language_name(detected_lang)
        
        try:
            # Create content for Gemini
            content_parts = []
            
            # Add image if present
            if image:
                content_parts.append(image)
            
            # Prepare the prompt based on whether image is present
            if image and user_message:
                # Both image and text present
                health_prompt = f"""
                You are a multilingual health awareness assistant for rural and semi-urban India.
                
                DETECTED LANGUAGE: {lang_name} ({detected_lang})
                
                The user has shared an image along with this question: "{user_message}"
                
                INSTRUCTIONS:
                1. Analyze the provided image carefully
                2. Respond in the SAME language as the user's question: {lang_name}
                3. Use simple, easy-to-understand language suitable for rural/semi-urban populations
                4. Focus ONLY on:
                   - Health-related observations from the image (symptoms, conditions, injuries, etc.)
                   - Preventive healthcare measures related to what you see
                   - General health tips and wellness advice
                   - When to seek professional medical help
                   - Basic first aid if applicable
                   - Hygiene and safety recommendations
                
                IMPORTANT RESTRICTIONS:
                - NEVER provide specific medical diagnoses
                - NEVER recommend specific medications or treatments
                - NEVER replace professional medical advice
                - Always suggest consulting local healthcare professionals, PHCs, or ASHA workers
                - Keep responses concise and practical for WhatsApp
                - Use culturally appropriate advice for Indian context
                - If the image shows serious conditions, emphasize immediate medical attention
                
                Analyze the image and answer the user's question in {lang_name}.
                """
            elif image and not user_message:
                # Only image present
                health_prompt = f"""
                You are a multilingual health awareness assistant for rural and semi-urban India.
                
                LANGUAGE: {lang_name} ({detected_lang})
                
                The user has shared an image without any specific question.
                
                INSTRUCTIONS:
                1. Analyze the provided image carefully
                2. Respond in {lang_name}
                3. Use simple, easy-to-understand language suitable for rural/semi-urban populations
                4. Provide general health observations and advice based on what you see
                5. Focus on:
                   - Health-related observations (if any)
                   - Preventive healthcare measures
                   - General wellness advice
                   - When to seek professional medical help
                   - Safety recommendations
                
                IMPORTANT RESTRICTIONS:
                - NEVER provide specific medical diagnoses
                - NEVER recommend specific medications
                - Always suggest consulting healthcare professionals for serious concerns
                - Keep responses practical for WhatsApp
                - If you see concerning health issues, emphasize medical consultation
                
                Describe what you observe and provide appropriate health guidance in {lang_name}.
                """
            else:
                # Only text present (original functionality)
                health_prompt = f"""
                You are a multilingual health awareness assistant for rural and semi-urban India. 
                
                DETECTED LANGUAGE: {lang_name} ({detected_lang})
                
                INSTRUCTIONS:
                1. Respond in the SAME language as the user's question: {lang_name}
                2. Use simple, easy-to-understand language suitable for rural/semi-urban populations
                3. Focus ONLY on:
                   - Preventive healthcare measures
                   - General health tips and wellness advice  
                   - Recognizing disease symptoms for awareness
                   - Encouraging healthy lifestyle habits
                   - When to seek professional medical help
                   - Basic hygiene and sanitation practices
                   - Nutrition and dietary advice for prevention
                
                IMPORTANT RESTRICTIONS:
                - NEVER provide specific medical diagnoses
                - NEVER recommend specific medications or treatments
                - NEVER replace professional medical advice
                - Always suggest consulting local healthcare professionals, PHCs, or ASHA workers
                - Keep responses concise and practical for WhatsApp
                - Use culturally appropriate advice for Indian context
                - Mention government healthcare schemes when relevant (Ayushman Bharat, etc.)
                
                USER QUESTION (in {lang_name}): {user_message}
                
                Provide helpful health awareness information in {lang_name}, keeping it simple and culturally appropriate for rural India.
                """
            
            # Add the prompt to content parts
            content_parts.append(health_prompt)
            
            # Generate response
            response = model.generate_content(content_parts)
            
            # Add disclaimer in the detected language
            disclaimers = {
                'en': "\n\n⚠️ *Remember: This is general health information. Always consult a healthcare professional, PHC, or ASHA worker for personalized medical advice.*",
                'hi': "\n\n⚠️ *याद रखें: यह सामान्य स्वास्थ्य जानकारी है। व्यक्तिगत चिकित्सा सलाह के लिए हमेशा स्वास्थ्य पेशेवर, PHC या आशा कार्यकर्ता से सलाह लें।*",
                'te': "\n\n⚠️ *గుర్తుంచుకోండి: ఇది సాధారణ ఆరోగ్య సమాచారం. వ్యక్తిగత వైద్య సలహా కోసం ఎల్లప్పుడూ ఆరోగ్య నిపుణుడు, PHC లేదా ఆశా కార్యకర్తను సంప్రదించండి.*"
            }
            
            disclaimer = disclaimers.get(detected_lang, disclaimers['en'])
            
            bot_response = response.text + disclaimer
            
            # Add image processing confirmation if image was processed
            if image:
                image_confirmations = {
                    'en': "\n📷 *Image analyzed successfully*",
                    'hi': "\n📷 *छवि का सफलतापूर्वक विश्लेषण किया गया*",
                    'te': "\n📷 *చిత్రం విజయవంతంగా విశ్లేషించబడింది*"
                }
                confirmation = image_confirmations.get(detected_lang, image_confirmations['en'])
                bot_response = confirmation + "\n\n" + bot_response
            
            dispatcher.utter_message(text=bot_response)
            
        except Exception as e:
            print(f"Error in health advice action: {e}")
            # Error message in detected language
            error_messages = {
                'en': "Sorry, I couldn't process your request right now. Please try again.",
                'hi': "क्षमा करें, मैं अभी आपके अनुरोध को संसाधित नहीं कर सका। कृपया पुनः प्रयास करें।",
                'te': "క్షమించండి, నేను ఇప్పుడు మీ అభ్యర్థనను ప్రాసెస్ చేయలేకపోయాను. దయచేసి మళ్లీ ప్రయత్నించండి।"
            }
            
            error_msg = error_messages.get(detected_lang, error_messages['en'])
            dispatcher.utter_message(text=error_msg)
        
        return []

class ActionSymptomCheckerMultilingual(Action):
    
    def name(self) -> Text:
        return "action_symptom_checker_multilingual"
    
    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        
        # Use the same multilingual logic as health advice
        health_action = ActionHealthAdviceMultilingual()
        return health_action.run(dispatcher, tracker, domain)


class WeekLinksExtractor:
    """
    Simple extractor to get links for N recent weeks only
    """
    
    def __init__(self):
        self.base_url = "https://idsp.mohfw.gov.in"
        self.weekly_outbreaks_url = f"{self.base_url}/index4.php?lang=1&level=0&linkid=406&lid=3689"
    
    def get_n_weeks_links(self, n: int = 4) -> List[Dict[str, str]]:
        """
        Get links for N most recent weeks
        
        Args:
            n: Number of recent weeks to get links for (default 4)
            
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
            
            print(f"✅ Found {len(recent_links)} recent week links")
            
            return recent_links
            
        except Exception as e:
            print(f"❌ Error fetching week links: {e}")
            return []
    
    def _extract_week_info(self, text: str, href: str) -> Dict[str, int]:
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
        
        # Default fallback
        return {'week': 1, 'year': 2025}


class ActionDiseaseOutbreakInfo(Action):
    
    def name(self) -> Text:
        return "action_disease_outbreak_info"
    
    def detect_language(self, text: str) -> str:
        """Detect the language of input text using Gemini"""
        try:
            genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
            model = genai.GenerativeModel('gemini-1.5-flash')
            
            detection_prompt = f"""
            Detect the language of this text and respond with ONLY the language code:
            - en (English)
            - hi (Hindi) 
            - te (Telugu)
            
            Text: "{text}"
            
            Respond with only the language code (e.g., "hi", "en", "te").
            """
            
            response = model.generate_content(detection_prompt)
            detected_lang = response.text.strip().lower()
            
            # Validate the detected language
            valid_langs = ['en', 'hi', 'te']
            return detected_lang if detected_lang in valid_langs else 'en'
            
        except Exception as e:
            print(f"Language detection error: {e}")
            return 'en'  # Default to English
    
    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        
        try:
            # Get the latest message from user
            latest_message = tracker.latest_message.get("text", "")
            
            # Detect language
            detected_lang = self.detect_language(latest_message)
            
            # Get recent disease outbreak data
            extractor = WeekLinksExtractor()
            outbreak_links = extractor.get_n_weeks_links(4)  # Get 4 weeks by default
            
            if not outbreak_links:
                # Error messages in detected language
                error_messages = {
                    'en': "Sorry, I couldn't fetch the latest disease outbreak information right now. Please try again later.",
                    'hi': "क्षमा करें, मैं अभी नवीनतम बीमारी के प्रकोप की जानकारी प्राप्त नहीं कर सका। कृपया बाद में पुनः प्रयास करें।",
                    'te': "క్షమించండి, నేను ఇప్పుడు తాజా వ్యాధి వ్యాప్తి సమాచారాన్ని పొందలేకపోయాను. దయచేసి తర్వాత మళ్లీ ప్రయత్నించండి।"
                }
                dispatcher.utter_message(text=error_messages.get(detected_lang, error_messages['en']))
                return []
            
            # Prepare multilingual response
            intro_messages = {
                'en': "🦠 **Latest Disease Outbreak Information from Ministry of Health & Family Welfare:**\n\n",
                'hi': "🦠 **स्वास्थ्य और परिवार कल्याण मंत्रालय से नवीनतम बीमारी प्रकोप की जानकारी:**\n\n",
                'te': "🦠 **ఆరోగ్య మరియు కుటుంబ సంక్షేమ మంత్రిత్వ శాఖ నుండి తాజా వ్యాధి వ్యాప్తి సమాచారం:**\n\n"
            }
            
            week_labels = {
                'en': "Week",
                'hi': "सप्ताह", 
                'te': "వారం"
            }
            
            access_labels = {
                'en': "📄 Access Report:",
                'hi': "📄 रिपोर्ट तक पहुंचें:",
                'te': "📄 రిపోర్ట్‌ను యాక్సెస్ చేయండి:"
            }
            
            # Build response message
            response_msg = intro_messages.get(detected_lang, intro_messages['en'])
            
            for i, link in enumerate(outbreak_links, 1):
                week_label = week_labels.get(detected_lang, week_labels['en'])
                access_label = access_labels.get(detected_lang, access_labels['en'])
                
                response_msg += f"**{i}. {week_label} {link['week']}, {link['year']}**\n"
                response_msg += f"{access_label} {link['url']}\n\n"
            
            # Add guidance message
            guidance_messages = {
                'en': "💡 **Note:** These reports contain official information about disease outbreaks in different states. Click the links to view the detailed PDF reports from the Integrated Disease Surveillance Programme (IDSP).",
                'hi': "💡 **नोट:** इन रिपोर्टों में विभिन्न राज्यों में बीमारी के प्रकोप के बारे में आधिकारिक जानकारी है। एकीकृत रोग निगरानी कार्यक्रम (आईडीएसपी) से विस्तृत पीडीएफ रिपोर्ट देखने के लिए लिंक पर क्लिक करें।",
                'te': "💡 **గమనిక:** ఈ నివేదికలు వివిధ రాష్ట్రాలలో వ్యాధి వ్యాప్తికి సంబంధించిన అధికారిక సమాచారాన్ని కలిగి ఉన్నాయి. ఇంటిగ్రేటెడ్ డిసీజ్ సర్వైలెన్స్ ప్రోగ్రామ్ (IDSP) నుండి వివరణాత్మక PDF నివేదికలను చూడటానికి లింక్‌లపై క్లిక్ చేయండి."
            }
            
            response_msg += "\n" + guidance_messages.get(detected_lang, guidance_messages['en'])
            
            dispatcher.utter_message(text=response_msg)
            
        except Exception as e:
            print(f"Error in disease outbreak action: {e}")
            # Error message in detected language
            error_messages = {
                'en': "Sorry, I couldn't fetch the disease outbreak information right now. Please try again later.",
                'hi': "क्षमा करें, मैं अभी बीमारी के प्रकोप की जानकारी प्राप्त नहीं कर सका। कृपया बाद में पुनः प्रयास करें।",
                'te': "క్షమించండి, నేను ఇప్పుడు వ్యాధి వ్యాప్తి సమాచారాన్ని పొందలేకపోయాను. దయచేసి తర్వాత మళ్లీ ప్రయత్నించండి।"
            }
            
            detected_lang = self.detect_language(tracker.latest_message.get("text", ""))
            error_msg = error_messages.get(detected_lang, error_messages['en'])
            dispatcher.utter_message(text=error_msg)
        
        return []