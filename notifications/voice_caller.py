"""
Voice Call Trigger Module

Triggers voice calls for critical alerts using:
- Twilio API
- AWS SNS
- Custom SIP integration
"""

from __future__ import annotations

from typing import Optional, Dict, List
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class VoiceCallRequest:
    """Voice call request."""
    to_number: str
    message: str
    from_number: Optional[str] = None
    retry_count: int = 0
    priority: str = "normal"  # normal, high, emergency


class TwilioVoiceCaller:
    """
    Voice call integration using Twilio.
    """
    
    def __init__(
        self,
        account_sid: str,
        auth_token: str,
        from_number: str
    ):
        self.account_sid = account_sid
        self.auth_token = auth_token
        self.from_number = from_number
        self._client = None
    
    def _get_client(self):
        """Get or create Twilio client."""
        if self._client is None:
            try:
                from twilio.rest import Client
                self._client = Client(self.account_sid, self.auth_token)
            except ImportError:
                logger.error("Twilio not installed")
                raise
        return self._client
    
    def make_call(
        self,
        request: VoiceCallRequest
    ) -> bool:
        """
        Initiate voice call.
        
        Args:
            request: VoiceCallRequest with details
        
        Returns:
            True if call initiated successfully
        """
        try:
            client = self._get_client()
            
            # Create TwiML for spoken message
            twiml = f"""
            <Response>
                <Say voice="alice">
                    Critical Alert from Network Operations Center.
                    {request.message}
                    Please acknowledge.
                </Say>
                <Gather action="/ack" numDigits="1">
                    <Say>Press 1 to acknowledge this alert.</Say>
                </Gather>
            </Response>
            """
            
            call = client.calls.create(
                twiml=twiml,
                to=request.to_number,
                from_=request.from_number or self.from_number
            )
            
            logger.info(f"Voice call initiated: {call.sid} to {request.to_number}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to make voice call: {e}")
            return False
    
    def check_call_status(self, call_sid: str) -> Optional[str]:
        """Check status of a call."""
        try:
            client = self._get_client()
            call = client.calls(call_sid).fetch()
            return call.status
        except Exception as e:
            logger.error(f"Failed to check call status: {e}")
            return None


class AWSSNSVoiceCaller:
    """
    Voice call using AWS SNS.
    """
    
    def __init__(
        self,
        aws_access_key: str,
        aws_secret_key: str,
        region: str = "us-east-1"
    ):
        self.aws_access_key = aws_access_key
        self.aws_secret_key = aws_secret_key
        self.region = region
        self._client = None
    
    def _get_client(self):
        """Get SNS client."""
        if self._client is None:
            try:
                import boto3
                self._client = boto3.client(
                    "sns",
                    aws_access_key_id=self.aws_access_key,
                    aws_secret_access_key=self.aws_secret_key,
                    region_name=self.region
                )
            except ImportError:
                logger.error("boto3 not installed")
                raise
        return self._client
    
    def make_call(self, request: VoiceCallRequest) -> bool:
        """Make voice call via SNS."""
        try:
            client = self._get_client()
            
            # Format phone number (E.164)
            phone = request.to_number
            if not phone.startswith("+"):
                phone = "+" + phone
            
            response = client.publish(
                PhoneNumber=phone,
                Message=request.message,
                MessageAttributes={
                    "AWS.SNS.SMS.SMSType": {
                        "DataType": "String",
                        "StringValue": "Transactional"
                    }
                }
            )
            
            logger.info(f"SNS notification sent: {response['MessageId']}")
            return True
            
        except Exception as e:
            logger.error(f"Failed SNS call: {e}")
            return False


class VoiceCallManager:
    """
    Manages voice call triggering with fallback and escalation.
    """
    
    def __init__(self):
        self.providers: List = []
        self.contact_numbers: Dict[str, List[str]] = {}
        self.escalation_policy: Dict[str, int] = {}
    
    def add_provider(self, provider) -> None:
        """Add a voice call provider."""
        self.providers.append(provider)
    
    def register_contact(
        self,
        contact_id: str,
        phone_numbers: List[str]
    ) -> None:
        """Register contact phone numbers."""
        self.contact_numbers[contact_id] = phone_numbers
    
    def trigger_alert(
        self,
        contact_id: str,
        message: str,
        priority: str = "high"
    ) -> Dict[str, bool]:
        """
        Trigger voice calls to all numbers for contact.
        
        Args:
            contact_id: Contact to call
            message: Message to speak
            priority: Alert priority
        
        Returns:
            Dict mapping number to success status
        """
        numbers = self.contact_numbers.get(contact_id, [])
        results = {}
        
        for number in numbers:
            request = VoiceCallRequest(
                to_number=number,
                message=message,
                priority=priority
            )
            
            # Try providers in order
            for provider in self.providers:
                success = provider.make_call(request)
                results[number] = success
                
                if success:
                    break
            else:
                results[number] = False
        
        return results
    
    def should_call(
        self,
        severity: str,
        time_of_day: str = "business_hours"
    ) -> bool:
        """
        Determine if voice call should be triggered.
        
        Args:
            severity: Alert severity
            time_of_day: "business_hours" or "after_hours"
        
        Returns:
            True if call should be made
        """
        # Always call for emergency
        if severity == "emergency":
            return True
        
        # Call for critical during/after hours
        if severity == "critical":
            return True
        
        # Call for high only after hours
        if severity == "high" and time_of_day == "after_hours":
            return True
        
        return False


class TextToSpeechFormatter:
    """
    Formats alert messages for text-to-speech.
    """
    
    @staticmethod
    def format_for_voice(message: str) -> str:
        """
        Format message for optimal TTS.
        
        - Abbreviations spelled out
        - Numbers spoken clearly
        - Punctuation for pauses
        """
        # Spell out common abbreviations
        replacements = {
            "CPU": "C P U",
            "MEM": "memory",
            "DISK": "disk",
            "NET": "network",
            "IP": "I P",
            "VPN": "V P N",
            "BGP": "B G P",
            "OSPF": "O S P F",
            "STP": "spanning tree",
            "VLAN": "V LAN",
            "WAN": "WAN",
            "LAN": "LAN",
            "HTTP": "H T T P",
            "HTTPS": "H T T P S",
            "SSH": "S S H",
            "NOC": "Network Operations Center",
            "%": "percent",
        }
        
        formatted = message
        for abbrev, spoken in replacements.items():
            formatted = formatted.replace(abbrev, spoken)
        
        # Add pauses
        formatted = formatted.replace(".", ". ")
        formatted = formatted.replace("!", "! ")
        
        return formatted
