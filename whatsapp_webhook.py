"""
Simple WhatsApp webhook handler for Health Bot
Uses Rasa REST API
"""
import os
import logging
import asyncio
import aiohttp
import requests
import base64
from io import BytesIO
from PIL import Image
from flask import Flask, request, Response
from twilio.rest import Client
from twilio.twiml.messaging_response import MessagingResponse
from dotenv import load_dotenv
import time
from datetime import datetime, timedelta

# Load environment variables
load_dotenv()

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Twilio client
twilio_client = Client(
    os.getenv("TWILIO_ACCOUNT_SID"),
    os.getenv("TWILIO_AUTH_TOKEN")
)

# Rasa server URL
RASA_SERVER_URL = os.getenv("RASA_SERVER_URL", "http://localhost:5005/webhooks/rest/webhook")

async def analyze_image_with_gemini(image_url: str, user_message: str = ""):
    """Analyze image using Gemini 2.5 Flash for health-related content"""
    try:
        import google.generativeai as genai
        
        # Configure Gemini API
        genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
        model = genai.GenerativeModel('gemini-2.5-flash')
        
        # Download the image with authentication for Twilio URLs
        headers = {}
        if 'api.twilio.com' in image_url:
            # For Twilio media URLs, use basic auth
            account_sid = os.getenv("TWILIO_ACCOUNT_SID")
            auth_token = os.getenv("TWILIO_AUTH_TOKEN")
            import requests
            response = requests.get(image_url, auth=(account_sid, auth_token))
        else:
            async with aiohttp.ClientSession() as session:
                async with session.get(image_url) as resp:
                    if resp.status == 200:
                        response_content = await resp.read()
                    else:
                        logger.error(f"Failed to download image: {resp.status}")
                        return "I couldn't download the image. Please try sending it again."
        
        if 'api.twilio.com' in image_url:
            if response.status_code != 200:
                logger.error(f"Failed to download Twilio image: {response.status_code}")
                return "I couldn't download the image. Please try sending it again."
            response_content = response.content
        
        # Validate image
        try:
            image = Image.open(BytesIO(response_content))
            logger.info(f"Image format: {image.format}, Size: {image.size}")
            
            # Convert to RGB if necessary
            if image.mode != 'RGB':
                image = image.convert('RGB')
                
        except Exception as e:
            logger.error(f"Invalid image format: {e}")
            return "I couldn't process this image format. Please send a clear photo (JPEG, PNG, etc.)."
        
        # Detect language from user message for response (improved detection)
        detected_lang = 'en'  # Default
        lang_name = 'English'
        
        if user_message and user_message.strip():
            # Enhanced language detection
            text_to_check = user_message.lower()
            
            # Hindi detection - check for Devanagari script and common Hindi words
            hindi_chars = any(char in user_message for char in 'अआइईउऊएऐओऔकखगघङचछजझञटठडढणतथदधनपफबभमयरलवशषसहक्षत्रज्ञ')
            hindi_words = any(word in text_to_check for word in ['kya', 'hai', 'mera', 'yeh', 'aur', 'mein', 'hoon', 'kaisa', 'kaise'])
            
            # Telugu detection - check for Telugu script and common Telugu words  
            telugu_chars = any(char in user_message for char in 'అఆఇఈఉఊఋఌఎఏఐఒఓఔకఖగఘఙచఛజఝఞటఠడఢణతథదధనపఫబభమయరలవశషసహళక్షత్రజ్ఞ')
            telugu_words = any(word in text_to_check for word in ['enti', 'ela', 'nenu', 'miru', 'emiti', 'enduku', 'ekkada'])
            
            if hindi_chars or hindi_words:
                detected_lang = 'hi'
                lang_name = 'Hindi'
            elif telugu_chars or telugu_words:
                detected_lang = 'te' 
                lang_name = 'Telugu'
                
            logger.info(f"Detected language: {lang_name} ({detected_lang}) from text: '{user_message[:50]}...'")
        else:
            logger.info(f"No text provided, using default language: {lang_name}")
        
        # Create ultra-concise health analysis prompt (strict WhatsApp limits)
        if user_message:
            if detected_lang == 'hi':
                health_prompt = f"""
                व्हाट्सऐप की 1600 वर्ण सीमा है। बहुत संक्षिप्त रहें।
                
                इस स्वास्थ्य छवि का विश्लेषण करें: "{user_message}"
                
                प्रारूप (अधिकतम 1000 वर्ण):
                🔍 दिख रहा है: [1 वाक्य अधिकतम]
                ⚠️ चिंता: सामान्य/हल्की/मध्यम/गंभीर
                💡 सलाह: [2-3 मुख्य बातें]
                🏥 कार्य: [डॉक्टर कब मिलें - 1 वाक्य]
                
                नियम:
                - अधिकतम 1000 वर्ण
                - केवल हिंदी में उत्तर दें
                - कोई निदान नहीं
                - संक्षिप्त और उपयोगी बनें
                
                मोबाइल मैसेजिंग के लिए छोटा रखें!
                """
            elif detected_lang == 'te':
                health_prompt = f"""
                వాట్సాప్ 1600 అక్షరాల పరిమితి ఉంది. చాలా సంక్షిప్తంగా ఉంచండి.
                
                ఈ ఆరోగ్య చిత్రాన్ని విశ్లేషించండి: "{user_message}"
                
                ఫార్మాట్ (గరిష్టంగా 1000 అక్షరాలు):
                🔍 కనిపిస్తుంది: [1 వాక్యం గరిష్టంగా]
                ⚠️ ఆందోళన: సాధారణం/తేలికపాటి/మధ్యమ/తీవ్రమైన
                💡 సలహా: [2-3 ముఖ్య విషయాలు]
                🏥 చర్య: [డాక్టర్ ఎప్పుడు చూడాలి - 1 వాక్యం]
                
                నియమాలు:
                - గరిష్టంగా 1000 అక్షరాలు
                - తెలుగులో మాత్రమే సమాధానం ఇవ్వండి
                - నిర్ధారణ చేయవద్దు
                - సంక్షిప్తంగా మరియు ఉపయోగకరంగా ఉండండి
                
                మొబైల్ సందేశ పంపడం కోసం చిన్నగా ఉంచండి!
                """
            else:  # English
                health_prompt = f"""
                URGENT: WhatsApp has 1600 char limit. Be EXTREMELY concise.
                
                Analyze this health image for: "{user_message}"
                
                FORMAT (MAX 1000 chars including emojis):
                🔍 What I see: [1 sentence max]
                ⚠️ Concern: Normal/Mild/Moderate/Serious
                💡 Advice: [2-3 bullet points max]
                🏥 Action: [When to see doctor - 1 sentence]
                
                CRITICAL RULES:
                - MAXIMUM 1000 characters total
                - English only
                - No detailed descriptions
                - No medical diagnoses
                - Be direct and helpful
                
                Keep it SHORT for mobile messaging!
                """
        else:
            if detected_lang == 'hi':
                health_prompt = f"""
                व्हाट्सऐप सीमा 1600 वर्ण। बेहद संक्षिप्त रहें।
                
                इस स्वास्थ्य छवि का त्वरित विश्लेषण करें।
                
                प्रारूप (अधिकतम 1000 वर्ण):
                🔍 दिख रहा है: [संक्षिप्त विवरण]
                ⚠️ चिंता: [स्तर]
                💡 सलाह: [मुख्य कार्य केवल]
                🏥 कार्य: [डॉक्टर का समय]
                
                नियम:
                - अधिकतम 1000 वर्ण
                - केवल हिंदी
                - उपयोगी लेकिन संक्षिप्त!
                """
            elif detected_lang == 'te':
                health_prompt = f"""
                వాట్సాప్ పరిమితి 1600 అక్షరాలు. చాలా సంక్షిప్తంగా ఉండండి.
                
                ఈ ఆరోగ్య చిత్రాన్ని త్వరగా విశ్లేషించండి.
                
                ఫార్మాట్ (గరిష్టంగా 1000 అక్షరాలు):
                🔍 కనిపిస్తుంది: [సంక్షిప్త వివరణ]
                ⚠️ ఆందోళన: [స్థాయి]
                💡 సలహా: [ముఖ్య చర్యలు మాత్రమే]
                🏥 చర్య: [డాక్టర్ సమయం]
                
                నియమాలు:
                - గరిష్టంగా 1000 అక్షరాలు
                - తెలుగు మాత్రమే
                - ఉపయోగకరంగా కానీ సంక్షిప్తంగా!
                """
            else:  # English
                health_prompt = f"""
                URGENT: WhatsApp limit 1600 chars. Be EXTREMELY brief.
                
                Analyze this health image quickly.
                
                FORMAT (MAX 1000 chars):
                🔍 What I see: [Brief description]
                ⚠️ Concern: Normal/Concerning/Urgent
                💡 Advice: [Key actions only]
                🏥 Action: [Doctor timing]
                
                RULES:
                - MAX 1000 characters
                - English only
                - No long explanations
                - Be helpful but concise!
                """
        
        # Generate response using Gemini 2.5 Flash
        response = model.generate_content([health_prompt, image])
        
        # Get initial response text
        initial_response = response.text
        
        # Add appropriate disclaimer based on language (shortened for WhatsApp)
        disclaimers = {
            'en': "\n\n⚠️ *AI analysis only. Consult doctor for diagnosis.*",
            'hi': "\n\n⚠️ *केवल AI विश्लेषण। निदान के लिए डॉक्टर से सलाह लें।*",
            'te': "\n\n⚠️ *AI విశ్లేషణ మాత్రమే। నిర్ధారణ కోసం వైద్యుడిని సంప్రదించండి।*"
        }
        
        disclaimer = disclaimers.get(detected_lang, disclaimers['en'])
        
        # Combine response and disclaimer
        full_response = initial_response + disclaimer
        
        # HARD LIMIT CHECK: If still too long, truncate aggressively
        if len(full_response) > 1200:
            logger.warning(f"Response too long ({len(full_response)} chars), truncating...")
            
            # Keep only the essential parts
            lines = initial_response.split('\n')
            truncated_lines = []
            char_count = 0
            
            for line in lines:
                if char_count + len(line) + len(disclaimer) < 1200:
                    truncated_lines.append(line)
                    char_count += len(line) + 1  # +1 for newline
                else:
                    break
            
            # If we have some content, use it; otherwise create a minimal response
            if truncated_lines:
                truncated_response = '\n'.join(truncated_lines)
                full_response = truncated_response + disclaimer
            else:
                # Emergency fallback - ultra-minimal response in detected language
                fallback_responses = {
                    'en': f"🔍 What I see: Skin condition visible\n⚠️ Concern: Moderate\n💡 Advice: Keep clean, see dermatologist\n🏥 Action: Visit doctor soon{disclaimer}",
                    'hi': f"🔍 दिख रहा है: त्वचा की समस्या\n⚠️ चिंता: मध्यम\n💡 सलाह: साफ रखें, डॉक्टर से मिलें\n🏥 कार्य: जल्दी डॉक्टर के पास जाएं{disclaimer}",
                    'te': f"🔍 కనిపిస్తుంది: చర్మ సమస్య\n⚠️ ఆందోళన: మధ్యమ\n💡 సలహా: శుభ్రంగా ఉంచండి, వైద్యుడిని చూడండి\n🏥 చర్య: త్వరగా డాక్టర్ దగ్గరకు వెళ్ళండి{disclaimer}"
                }
                full_response = fallback_responses.get(detected_lang, fallback_responses['en'])
        
        analysis_result = full_response
        
        logger.info(f"Gemini image analysis completed successfully")
        return analysis_result
        
    except Exception as e:
        logger.error(f"Gemini image analysis error: {e}")
        # Return helpful fallback based on detected language
        fallback_messages = {
            'en': "I had trouble analyzing your image. Please ensure it's a clear photo and try again, or describe what you're seeing so I can help.",
            'hi': "मुझे आपकी छवि का विश्लेषण करने में समस्या हुई। कृपया सुनिश्चित करें कि यह एक स्पष्ट फोटो है और पुनः प्रयास करें, या वर्णन करें कि आप क्या देख रहे हैं ताकि मैं मदद कर सकूं।",
            'te': "మీ చిత్రాన్ని విశ్లేషించడంలో నాకు ఇబ్బంది ఎదురైంది. దయచేసి ఇది స్పష్టమైన ఫోటో అని నిర్ధారించుకోండి మరియు మళ్లీ ప్రయత్నించండి, లేదా మీరు ఏమి చూస్తున్నారో వివరించండి తద్వారా నేను సహాయం చేయగలను."
        }
        return fallback_messages.get(detected_lang, fallback_messages['en'])

async def send_message_to_rasa(message: str, sender: str, image_url: str = None):
    """Send message to Rasa and get response"""
    try:
        # If there's an image, analyze it using Gemini 2.5 Flash
        if image_url:
            image_analysis = await analyze_image_with_gemini(image_url, message)
            # For images, send the analysis directly instead of going through Rasa
            return [{"text": image_analysis}]
        
        async with aiohttp.ClientSession() as session:
            payload = {
                "sender": sender,
                "message": message
            }
            
            # Add image URL to metadata if present
            if image_url:
                payload["metadata"] = {"image_url": image_url}
            
            async with session.post(RASA_SERVER_URL, json=payload) as resp:
                if resp.status == 200:
                    responses = await resp.json()
                    return responses
                else:
                    logger.error(f"Rasa server error: {resp.status}")
                    return [{"text": "Sorry, I'm having trouble right now. Please try again later."}]
                    
    except Exception as e:
        logger.error(f"Error communicating with Rasa: {e}")
        return [{"text": "Sorry, I'm having trouble right now. Please try again later."}]

def get_media_url(media_sid: str):
    """Get media URL from Twilio media SID with authentication"""
    try:
        # Get the media resource
        media = twilio_client.api.v2010.accounts(
            os.getenv("TWILIO_ACCOUNT_SID")
        ).messages.media(media_sid).fetch()
        
        # The media URI needs authentication, so we'll fetch the actual content
        account_sid = os.getenv("TWILIO_ACCOUNT_SID")
        auth_token = os.getenv("TWILIO_AUTH_TOKEN")
        
        # Construct authenticated URL
        media_url = f"https://api.twilio.com{media.uri}"
        
        # For Twilio media, we need to use basic auth
        response = requests.get(media_url, auth=(account_sid, auth_token))
        
        if response.status_code == 200:
            return media_url
        else:
            logger.error(f"Failed to fetch media: {response.status_code}")
            return None
        
    except Exception as e:
        logger.error(f"Error getting media URL: {e}")
        return None

class MessageRateLimiter:
    def __init__(self, daily_limit=9):
        self.daily_limit = daily_limit
        self.message_count = 0
        self.reset_time = datetime.now() + timedelta(days=1)
    
    def can_send_message(self):
        if datetime.now() > self.reset_time:
            self.message_count = 0
            self.reset_time = datetime.now() + timedelta(days=1)
        
        return self.message_count < self.daily_limit
    
    def increment_count(self):
        self.message_count += 1

rate_limiter = MessageRateLimiter()

def split_message(message: str, max_length: int = 1400) -> list:
    """Split long messages into chunks under WhatsApp's character limit"""
    if len(message) <= max_length:
        return [message]
    
    # Split by sentences first, then by length if needed
    sentences = message.split('. ')
    chunks = []
    current_chunk = ""
    
    for sentence in sentences:
        # Add period back if it was removed by split
        if not sentence.endswith('.') and sentence != sentences[-1]:
            sentence += '.'
            
        # Check if adding this sentence would exceed limit
        if len(current_chunk + sentence) > max_length:
            if current_chunk:
                chunks.append(current_chunk.strip())
                current_chunk = sentence
            else:
                # Single sentence is too long, split by words
                words = sentence.split(' ')
                for word in words:
                    if len(current_chunk + ' ' + word) > max_length:
                        if current_chunk:
                            chunks.append(current_chunk.strip())
                            current_chunk = word
                        else:
                            # Single word is too long, force split
                            chunks.append(word[:max_length])
                            current_chunk = word[max_length:]
                    else:
                        current_chunk += ' ' + word if current_chunk else word
        else:
            current_chunk += ' ' + sentence if current_chunk else sentence
    
    if current_chunk:
        chunks.append(current_chunk.strip())
    
    return chunks

def send_whatsapp_message(to: str, message: str):
    """Send message via Twilio WhatsApp with automatic splitting for long messages"""
    try:
        if not to.startswith("whatsapp:"):
            to = f"whatsapp:{to}"
        
        # Split message if it's too long
        message_chunks = split_message(message, max_length=1400)  # Leave room for part indicators
        
        for i, chunk in enumerate(message_chunks):
            if not rate_limiter.can_send_message():
                logger.warning(f"Daily message limit reached. Would send chunk {i+1} to {to}: {chunk}")
                return False
            
            # Add part indicator for multi-part messages
            if len(message_chunks) > 1:
                part_indicator = f"[Part {i+1}/{len(message_chunks)}]\n"
                chunk_with_indicator = part_indicator + chunk
                
                # Double-check final length doesn't exceed WhatsApp limit
                if len(chunk_with_indicator) > 1500:
                    # If still too long, truncate the chunk
                    available_space = 1500 - len(part_indicator)
                    chunk = chunk[:available_space-3] + "..."
                    chunk_with_indicator = part_indicator + chunk
            else:
                chunk_with_indicator = chunk
            
            # Send actual message via Twilio
            twilio_message = twilio_client.messages.create(
                body=chunk_with_indicator,
                from_='whatsapp:+14155238886',  # Standard Twilio sandbox number
                to=to
            )
            logger.info(f"Sent WhatsApp message part {i+1}/{len(message_chunks)}: {twilio_message.sid}")
            rate_limiter.increment_count()
            
            # Small delay between parts to ensure proper ordering
            if len(message_chunks) > 1 and i < len(message_chunks) - 1:
                import time
                time.sleep(1)
        
        return True
        
    except Exception as e:
        if "exceeded" in str(e) and "daily messages limit" in str(e):
            logger.error(f"Daily limit exceeded: {e}")
            return False
        logger.error(f"Error sending WhatsApp message: {e}")
        # Fallback to debug mode if sending fails
        logger.info(f"DEBUG - Would send to {to}: {message}")
        return False

@app.route("/", methods=["GET"])
def health_check():
    return {"status": "Health Bot WhatsApp Webhook is running!", "bot": "multilingual_health_assistant"}

@app.route("/whatsapp", methods=["POST"])
def whatsapp_webhook():
    """Handle incoming WhatsApp messages"""
    try:
        # Get message details
        sender = request.form.get('From', '')
        message_body = request.form.get('Body', '')
        num_media = int(request.form.get('NumMedia', 0))
        
        logger.info(f"Received from {sender}: {message_body} (Media: {num_media})")
        
        image_url = None
        
        # Check for media attachments (images)
        if num_media > 0:
            media_content_type = request.form.get('MediaContentType0', '')
            if media_content_type.startswith('image/'):
                # Get the direct media URL from Twilio
                image_url = request.form.get('MediaUrl0', '')
                if image_url:
                    logger.info(f"Image received: {image_url}")
                    
                    # Analyze image with Gemini 2.5 Flash
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    image_analysis = loop.run_until_complete(
                        analyze_image_with_gemini(image_url, message_body)
                    )
                    loop.close()
                    
                    # Send image analysis response directly
                    send_whatsapp_message(sender, image_analysis)
                    
                    # Return early - no need to process through Rasa for images
                    resp = MessagingResponse()
                    return Response(str(resp), mimetype="text/xml")
        
        if sender and message_body:
            # Clean sender ID
            clean_sender = sender.replace("whatsapp:", "")
            
            # Send to Rasa and get responses (for text-only messages)
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            responses = loop.run_until_complete(
                send_message_to_rasa(message_body, clean_sender)
            )
            loop.close()
            
            # Send responses back via WhatsApp
            for response in responses:
                if "text" in response:
                    send_whatsapp_message(sender, response["text"])
        else:
            # Send a help message if no valid input
            help_message = "Hi! I'm your health assistant. You can:\n• Ask health questions in English, Hindi, or Telugu\n• Send images with health-related questions\n• Get general health advice and wellness tips"
            send_whatsapp_message(sender, help_message)
        
        # Return empty TwiML response
        resp = MessagingResponse()
        return Response(str(resp), mimetype="text/xml")
        
    except Exception as e:
        logger.error(f"Error in webhook: {e}")
        resp = MessagingResponse()
        return Response(str(resp), mimetype="text/xml")

if __name__ == "__main__":
    print("🏥 Starting Health Bot WhatsApp Webhook...")
    print("📱 Make sure Rasa server is running on port 5005")
    app.run(host="0.0.0.0", port=5000, debug=False)
