"""
AI-powered wine matching using Google Gemini 2.5 Flash
"""

import os
import json
import logging
from typing import Optional, Dict, Any, List
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Try to import AI libraries, handle gracefully if not available
try:
    import google.generativeai as genai
    GOOGLE_AI_AVAILABLE = True
    logger.info("Google Generative AI library loaded successfully")
except ImportError as e:
    genai = None
    GOOGLE_AI_AVAILABLE = False
    logger.warning(f"Google Generative AI library not available: {e}")

try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
    logger.info("OpenAI library loaded successfully")
except ImportError as e:
    OpenAI = None
    OPENAI_AVAILABLE = False
    logger.warning(f"OpenAI library not available: {e}")

@dataclass
class WineMatchResult:
    """Result of AI wine matching"""
    is_match: bool
    confidence_score: float  # 0-100
    match_type: str  # exact, partial, different, uncertain
    reasoning: str
    details: Optional[Dict[str, Any]] = None

@dataclass
class WineStyleSimplificationResult:
    """Result of AI wine style simplification"""
    simplified_style: str
    confidence_score: float  # 0-100
    original_style: str
    reasoning: Optional[str] = None

@dataclass
class FoodPairingResult:
    """Result of AI food pairing suggestions"""
    pairings: List[str]  # Simple one-word labels like ["fish", "poultry", "cheese"]
    confidence_score: float  # 0-100
    reasoning: Optional[str] = None

class GeminiWineMatcher:
    """AI-powered wine matcher using Google Gemini with OpenAI fallback"""
    
    def __init__(self):
        self.gemini_model = None
        self.openai_client = None
        
        # Configure Gemini API
        if GOOGLE_AI_AVAILABLE:
            api_key = os.getenv("GEMINI_API_KEY")
            if api_key:
                try:
                    genai.configure(api_key=api_key)
                    self.gemini_model = genai.GenerativeModel('gemini-2.0-flash-exp')
                    logger.info("Gemini AI wine matcher initialized")
                except Exception as e:
                    logger.error(f"Failed to initialize Gemini: {e}")
            else:
                logger.warning("GEMINI_API_KEY not found")
        
        # Configure OpenAI API as fallback
        if OPENAI_AVAILABLE:
            api_key = os.getenv("OPENAI_API_KEY")
            if api_key:
                try:
                    self.openai_client = OpenAI(api_key=api_key)
                    logger.info("OpenAI client initialized as fallback")
                except Exception as e:
                    logger.error(f"Failed to initialize OpenAI: {e}")
            else:
                logger.warning("OPENAI_API_KEY not found")
        
        if not self.gemini_model and not self.openai_client:
            logger.warning("No AI services available. Using fallback string matching.")
    
    @property
    def model(self):
        """Backward compatibility - returns True if any AI service is available"""
        return self.gemini_model or self.openai_client
    
    async def match_wines(self, vivino_wine_name: str, systembolaget_wine_name: str, 
                         vivino_rating: float = None, sb_price: float = None,
                         sb_country: str = None, sb_style: str = None) -> WineMatchResult:
        """
        Use Gemini AI to determine if two wine names refer to the same wine
        
        Args:
            vivino_wine_name: Wine name from Vivino
            systembolaget_wine_name: Wine name from Systembolaget
            vivino_rating: Vivino rating (optional context)
            sb_price: Systembolaget price (optional context)
            sb_country: Wine country (optional context)
            sb_style: Wine style (optional context)
        
        Returns:
            WineMatchResult with AI analysis
        """
        
        if not self.model:
            # Fallback to simple string matching if Gemini not available
            return self._fallback_match(vivino_wine_name, systembolaget_wine_name)
        
        try:
            prompt = self._build_prompt(
                vivino_wine_name, systembolaget_wine_name, 
                vivino_rating, sb_price, sb_country, sb_style
            )
            
            response = await self._call_gemini(prompt)
            return self._parse_response(response, vivino_wine_name, systembolaget_wine_name)
            
        except Exception as e:
            logger.error(f"Gemini AI matching failed: {e}")
            return self._fallback_match(vivino_wine_name, systembolaget_wine_name)
    
    def _build_prompt(self, vivino_name: str, sb_name: str, 
                     rating: float = None, price: float = None, 
                     country: str = None, style: str = None) -> str:
        """Build the prompt for Gemini AI"""
        
        context_info = []
        if rating:
            context_info.append(f"Vivino rating: {rating}/5")
        if price:
            context_info.append(f"Price: {price} SEK")
        if country:
            context_info.append(f"Country: {country}")
        if style:
            context_info.append(f"Style: {style}")
        
        context_str = "\n".join(context_info) if context_info else "No additional context available"
        
        prompt = f"""You are an expert wine sommelier and data analyst. Your task is to determine if two wine names refer to the same wine product.

WINE 1 (from Vivino): "{vivino_name}"
WINE 2 (from Systembolaget): "{sb_name}"

Additional context:
{context_str}

Analyze these wine names considering:
1. Producer/winery names (may be abbreviated or in different languages)
2. Wine names and appellations
3. Vintage years (if present)
4. Grape varieties or wine styles
5. Regional variations in naming
6. Common abbreviations in wine industry
7. Translation differences (Swedish/English/other languages)

Consider that:
- Systembolaget may use Swedish translations or local naming conventions
- Producer names might be shortened or stylized differently
- Vintage years may be omitted or different between sources
- Same wine may have different marketing names in different markets

Please respond with a JSON object in this exact format:
{{
    "is_match": true/false,
    "confidence_score": <0-100>,
    "match_type": "exact|partial|different|uncertain",
    "reasoning": "<detailed explanation of your analysis>",
    "key_factors": [
        "<factor1>",
        "<factor2>"
    ]
}}

Match types:
- "exact": Same wine, high confidence (90-100%)
- "partial": Likely same wine with some uncertainty (60-89%)
- "different": Clearly different wines (0-39%)
- "uncertain": Cannot determine with confidence (40-59%)

Be conservative but thorough in your analysis. Consider wine industry naming conventions and regional variations."""

        return prompt
    
    async def _call_gemini(self, prompt: str) -> str:
        """Call AI service with the prompt (Gemini first, OpenAI fallback)"""
        
        # Try Gemini first
        if self.gemini_model:
            try:
                response = self.gemini_model.generate_content(prompt)
                logger.debug("Used Gemini AI for response")
                return response.text
            except Exception as e:
                logger.warning(f"Gemini API call failed: {e}, trying OpenAI fallback")
        
        # Fall back to OpenAI
        if self.openai_client:
            try:
                response = await self._call_openai(prompt)
                logger.info("Used OpenAI as fallback")
                return response
            except Exception as e:
                logger.error(f"OpenAI API call failed: {e}")
                raise
        
        # No AI services available
        raise Exception("No AI services available")
    
    async def _call_openai(self, prompt: str) -> str:
        """Call OpenAI API with the prompt"""
        try:
            response = self.openai_client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are an expert wine sommelier and data analyst."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=1000
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"OpenAI API call failed: {e}")
            raise
    
    def _parse_response(self, response: str, vivino_name: str, sb_name: str) -> WineMatchResult:
        """Parse Gemini's JSON response"""
        try:
            # Extract JSON from response (in case there's extra text)
            response_clean = response.strip()
            if response_clean.startswith("```json"):
                response_clean = response_clean[7:]
            if response_clean.endswith("```"):
                response_clean = response_clean[:-3]
            
            data = json.loads(response_clean)
            
            return WineMatchResult(
                is_match=data.get("is_match", False),
                confidence_score=float(data.get("confidence_score", 0)),
                match_type=data.get("match_type", "uncertain"),
                reasoning=data.get("reasoning", "No reasoning provided"),
                details={
                    "key_factors": data.get("key_factors", []),
                    "vivino_name": vivino_name,
                    "systembolaget_name": sb_name
                }
            )
            
        except (json.JSONDecodeError, KeyError) as e:
            logger.error(f"Failed to parse Gemini response: {e}")
            logger.error(f"Raw response: {response}")
            
            # Fallback parsing - try to extract key information
            is_match = "true" in response.lower() and "is_match" in response.lower()
            confidence = 50.0  # Default uncertain confidence
            
            return WineMatchResult(
                is_match=is_match,
                confidence_score=confidence,
                match_type="uncertain",
                reasoning=f"Could not parse AI response properly. Raw: {response[:200]}...",
                details={"parse_error": True}
            )
    
    def _fallback_match(self, vivino_name: str, sb_name: str) -> WineMatchResult:
        """Fallback to simple string matching when AI is not available"""
        from difflib import SequenceMatcher
        import unicodedata
        import re
        
        def normalize_name(name: str) -> str:
            # Remove years and common wine terms
            name = re.sub(r"\b20\d{2}\b", "", name.lower())
            name = re.sub(r"\b(wine|vin|rouge|blanc|rosé|red|white|rose)\b", "", name)
            # Normalize unicode
            name = "".join(char for char in unicodedata.normalize("NFD", name) 
                          if unicodedata.category(char) != "Mn")
            return " ".join(name.split())
        
        norm_vivino = normalize_name(vivino_name)
        norm_sb = normalize_name(sb_name)
        
        # Calculate similarity
        similarity = SequenceMatcher(None, norm_vivino, norm_sb).ratio()
        confidence = round(similarity * 100, 1)
        
        # Determine match type based on similarity
        if confidence >= 90:
            match_type = "exact"
            is_match = True
        elif confidence >= 70:
            match_type = "partial" 
            is_match = True
        elif confidence >= 40:
            match_type = "uncertain"
            is_match = False
        else:
            match_type = "different"
            is_match = False
        
        return WineMatchResult(
            is_match=is_match,
            confidence_score=confidence,
            match_type=match_type,
            reasoning=f"Fallback string matching: {confidence}% similarity between normalized names",
            details={
                "fallback_mode": True,
                "normalized_vivino": norm_vivino,
                "normalized_systembolaget": norm_sb
            }
        )
    
    async def simplify_wine_style(self, original_style: str) -> WineStyleSimplificationResult:
        """
        Use Gemini AI to simplify complex wine styles into basic categories
        
        Args:
            original_style: Complex wine style like "Portuguese Douro Red" or "Spanish Rioja Red"
        
        Returns:
            WineStyleSimplificationResult with simplified style
        """
        
        if not self.model:
            # Fallback to simple categorization if Gemini not available
            return self._fallback_simplify_style(original_style)
        
        if not original_style or original_style.strip() == "":
            return WineStyleSimplificationResult(
                simplified_style="Unknown",
                confidence_score=100.0,
                original_style=original_style or "",
                reasoning="Empty or null wine style"
            )
        
        try:
            prompt = self._build_style_simplification_prompt(original_style)
            response = await self._call_gemini(prompt)
            return self._parse_style_response(response, original_style)
            
        except Exception as e:
            logger.error(f"Gemini AI style simplification failed: {e}")
            return self._fallback_simplify_style(original_style)
    
    def _build_style_simplification_prompt(self, original_style: str) -> str:
        """Build the prompt for wine style simplification"""
        
        prompt = f"""You are an expert wine sommelier. Your task is to simplify complex, regional wine style names into basic, user-friendly categories.

ORIGINAL WINE STYLE: "{original_style}"

Please simplify this wine style into one of these basic categories:
- "Red Wine" (for all red wines regardless of region/appellation)
- "White Wine" (for all white wines regardless of region/appellation) 
- "Rosé Wine" (for all rosé/pink wines)
- "Sparkling Wine" (for champagne, cava, prosecco, etc.)
- "Dessert Wine" (for sweet/dessert wines)
- "Fortified Wine" (for port, sherry, etc.)
- "Unknown" (if style cannot be determined)

Guidelines:
1. Remove regional/geographical information (e.g., "Portuguese Douro" → "Red Wine")
2. Remove specific appellations (e.g., "Spanish Rioja Red" → "Red Wine")
3. Remove grape variety specifics (e.g., "Burgundy Pinot Noir" → "Red Wine")
4. Keep only the basic wine type/color
5. Use simple, consumer-friendly language
6. Be consistent with categorization

Examples:
- "Portuguese Douro Red" → "Red Wine"
- "Spanish Ribera Del Duero Red" → "Red Wine" 
- "French Champagne" → "Sparkling Wine"
- "Italian Chianti Classico" → "Red Wine"
- "German Riesling" → "White Wine"
- "Nya Zeeland Sauvignon Blanc" → "White Wine"

Please respond with a JSON object in this exact format:
{{
    "simplified_style": "<basic category>",
    "confidence_score": <0-100>,
    "reasoning": "<brief explanation of your categorization>"
}}

Be confident in your categorization based on wine knowledge."""

        return prompt
    
    def _parse_style_response(self, response: str, original_style: str) -> WineStyleSimplificationResult:
        """Parse Gemini response for style simplification"""
        try:
            # Clean the response to extract JSON
            response_clean = response.strip()
            if response_clean.startswith("```json"):
                response_clean = response_clean[7:]
            if response_clean.endswith("```"):
                response_clean = response_clean[:-3]
            response_clean = response_clean.strip()
            
            data = json.loads(response_clean)
            
            simplified_style = data.get("simplified_style", "Unknown")
            confidence_score = float(data.get("confidence_score", 50))
            reasoning = data.get("reasoning", "AI analysis completed")
            
            # Validate simplified style is in our expected categories
            valid_categories = {
                "Red Wine", "White Wine", "Rosé Wine", "Sparkling Wine", 
                "Dessert Wine", "Fortified Wine", "Unknown"
            }
            
            if simplified_style not in valid_categories:
                logger.warning(f"AI returned unexpected category: {simplified_style}, using fallback")
                return self._fallback_simplify_style(original_style)
            
            return WineStyleSimplificationResult(
                simplified_style=simplified_style,
                confidence_score=confidence_score,
                original_style=original_style,
                reasoning=reasoning
            )
            
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.error(f"Failed to parse AI style response: {e}, response: {response}")
            return self._fallback_simplify_style(original_style)
    
    def _fallback_simplify_style(self, original_style: str) -> WineStyleSimplificationResult:
        """Fallback style simplification using keyword matching"""
        if not original_style:
            return WineStyleSimplificationResult(
                simplified_style="Unknown",
                confidence_score=100.0,
                original_style="",
                reasoning="Empty style"
            )
        
        style_lower = original_style.lower()
        
        # Simple keyword-based categorization
        if any(word in style_lower for word in ['red', 'rouge', 'rosso', 'tinto', 'merlot', 'cabernet', 'pinot noir', 'chianti', 'rioja', 'douro']):
            return WineStyleSimplificationResult(
                simplified_style="Red Wine",
                confidence_score=80.0,
                original_style=original_style,
                reasoning="Fallback: Contains red wine keywords"
            )
        elif any(word in style_lower for word in ['white', 'blanc', 'bianco', 'blanco', 'chardonnay', 'sauvignon', 'riesling', 'albariño']):
            return WineStyleSimplificationResult(
                simplified_style="White Wine",
                confidence_score=80.0,
                original_style=original_style,
                reasoning="Fallback: Contains white wine keywords"
            )
        elif any(word in style_lower for word in ['rosé', 'rose', 'rosado']):
            return WineStyleSimplificationResult(
                simplified_style="Rosé Wine",
                confidence_score=85.0,
                original_style=original_style,
                reasoning="Fallback: Contains rosé keywords"
            )
        elif any(word in style_lower for word in ['sparkling', 'champagne', 'cava', 'prosecco', 'mousserande', 'bubbel']):
            return WineStyleSimplificationResult(
                simplified_style="Sparkling Wine",
                confidence_score=85.0,
                original_style=original_style,
                reasoning="Fallback: Contains sparkling wine keywords"
            )
        elif any(word in style_lower for word in ['port', 'sherry', 'madeira', 'marsala']):
            return WineStyleSimplificationResult(
                simplified_style="Fortified Wine",
                confidence_score=80.0,
                original_style=original_style,
                reasoning="Fallback: Contains fortified wine keywords"
            )
        elif any(word in style_lower for word in ['dessert', 'sweet', 'ice wine', 'sauternes']):
            return WineStyleSimplificationResult(
                simplified_style="Dessert Wine",
                confidence_score=75.0,
                original_style=original_style,
                reasoning="Fallback: Contains dessert wine keywords"
            )
        else:
            return WineStyleSimplificationResult(
                simplified_style="Unknown",
                confidence_score=50.0,
                original_style=original_style,
                reasoning="Fallback: Could not categorize wine style"
            )
    
    async def generate_food_pairings(self, wine_style: str = None, wine_name: str = None, 
                                   country: str = None, grape_varieties: List[str] = None,
                                   body: int = None, acidity: int = None) -> FoodPairingResult:
        """
        Use Gemini AI to generate simple food pairing suggestions
        
        Args:
            wine_style: Wine style (e.g., "Red Wine", "White Wine")
            wine_name: Name of the wine
            country: Wine country of origin
            grape_varieties: List of grape varieties
            body: Body rating (1-5)
            acidity: Acidity rating (1-5)
        
        Returns:
            FoodPairingResult with simple one-word pairing labels
        """
        
        if not self.model:
            # Fallback to simple pairing rules if Gemini not available
            return self._fallback_generate_pairings(wine_style)
        
        try:
            prompt = self._build_pairing_prompt(wine_style, wine_name, country, grape_varieties, body, acidity)
            response = await self._call_gemini(prompt)
            return self._parse_pairing_response(response)
            
        except Exception as e:
            logger.error(f"Gemini AI pairing generation failed: {e}")
            return self._fallback_generate_pairings(wine_style)
    
    def _build_pairing_prompt(self, wine_style: str = None, wine_name: str = None,
                             country: str = None, grape_varieties: List[str] = None,
                             body: int = None, acidity: int = None) -> str:
        """Build the prompt for food pairing generation"""
        
        wine_info = []
        if wine_style:
            wine_info.append(f"Style: {wine_style}")
        if wine_name:
            wine_info.append(f"Name: {wine_name}")
        if country:
            wine_info.append(f"Country: {country}")
        if grape_varieties:
            wine_info.append(f"Grapes: {', '.join(grape_varieties)}")
        if body:
            body_desc = ["Very Light", "Light", "Medium", "Full", "Very Full"][body-1] if 1 <= body <= 5 else "Unknown"
            wine_info.append(f"Body: {body_desc}")
        if acidity:
            acidity_desc = ["Very Low", "Low", "Medium", "High", "Very High"][acidity-1] if 1 <= acidity <= 5 else "Unknown"
            wine_info.append(f"Acidity: {acidity_desc}")
        
        wine_description = "\n".join(wine_info) if wine_info else "Limited wine information available"
        
        prompt = f"""You are an expert sommelier. Generate simple, one-word food pairing suggestions for this wine.

WINE INFORMATION:
{wine_description}

Please suggest 3-5 simple, one-word food categories that pair well with this wine. Use only these approved categories:

MEAT: beef, pork, lamb, game, poultry, chicken, duck
SEAFOOD: fish, shellfish, seafood, salmon, tuna
CHEESE: cheese, brie, cheddar, goat, blue
VEGETABLES: vegetables, salads, mushrooms, pasta
FRUIT: fruit, berries, citrus, tropical
DESSERT: chocolate, desserts, sweets, cake
BREAD: bread, crackers, nuts
SPICES: herbs, spices, garlic, pepper
OTHER: rice, grains, appetizers, tapas

Guidelines:
1. Choose 3-5 categories that best complement the wine
2. Consider wine style, body, acidity, and grape varieties
3. Use only the approved one-word categories above
4. Be specific and practical
5. Focus on foods that enhance the wine's characteristics

Examples:
- Red Wine with high tannins → ["beef", "lamb", "cheese", "chocolate"]
- Light White Wine → ["fish", "poultry", "salads", "fruit"]
- Sparkling Wine → ["appetizers", "shellfish", "cheese", "fruit"]

Please respond with a JSON object in this exact format:
{{
    "pairings": ["category1", "category2", "category3"],
    "confidence_score": <0-100>,
    "reasoning": "<brief explanation of why these pairings work>"
}}

Focus on creating practical, delicious combinations."""

        return prompt
    
    def _parse_pairing_response(self, response: str) -> FoodPairingResult:
        """Parse Gemini response for food pairings"""
        try:
            # Clean the response to extract JSON
            response_clean = response.strip()
            if response_clean.startswith("```json"):
                response_clean = response_clean[7:]
            if response_clean.endswith("```"):
                response_clean = response_clean[:-3]
            response_clean = response_clean.strip()
            
            data = json.loads(response_clean)
            
            pairings = data.get("pairings", [])
            confidence_score = float(data.get("confidence_score", 70))
            reasoning = data.get("reasoning", "AI pairing analysis")
            
            # Validate and clean pairings
            valid_categories = {
                "beef", "pork", "lamb", "game", "poultry", "chicken", "duck",
                "fish", "shellfish", "seafood", "salmon", "tuna",
                "cheese", "brie", "cheddar", "goat", "blue",
                "vegetables", "salads", "mushrooms", "pasta",
                "fruit", "berries", "citrus", "tropical",
                "chocolate", "desserts", "sweets", "cake",
                "bread", "crackers", "nuts",
                "herbs", "spices", "garlic", "pepper",
                "rice", "grains", "appetizers", "tapas"
            }
            
            # Filter and limit pairings
            filtered_pairings = [p.lower() for p in pairings if p.lower() in valid_categories][:5]
            
            if not filtered_pairings:
                logger.warning(f"AI returned invalid pairings: {pairings}, using fallback")
                return self._fallback_generate_pairings()
            
            return FoodPairingResult(
                pairings=filtered_pairings,
                confidence_score=confidence_score,
                reasoning=reasoning
            )
            
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.error(f"Failed to parse AI pairing response: {e}, response: {response}")
            return self._fallback_generate_pairings()
    
    def _fallback_generate_pairings(self, wine_style: str = None) -> FoodPairingResult:
        """Fallback pairing generation using simple rules"""
        
        if not wine_style:
            return FoodPairingResult(
                pairings=["cheese", "fruit", "bread"],
                confidence_score=50.0,
                reasoning="Fallback: Generic pairing suggestions"
            )
        
        style_lower = wine_style.lower()
        
        # Simple rule-based pairings
        if "red" in style_lower:
            return FoodPairingResult(
                pairings=["beef", "lamb", "cheese", "chocolate"],
                confidence_score=75.0,
                reasoning="Fallback: Red wine pairing rules"
            )
        elif "white" in style_lower:
            return FoodPairingResult(
                pairings=["fish", "poultry", "salads", "cheese"],
                confidence_score=75.0,
                reasoning="Fallback: White wine pairing rules"
            )
        elif "sparkling" in style_lower:
            return FoodPairingResult(
                pairings=["appetizers", "shellfish", "fruit", "cheese"],
                confidence_score=75.0,
                reasoning="Fallback: Sparkling wine pairing rules"
            )
        elif "rosé" in style_lower or "rose" in style_lower:
            return FoodPairingResult(
                pairings=["fish", "poultry", "salads", "fruit"],
                confidence_score=75.0,
                reasoning="Fallback: Rosé wine pairing rules"
            )
        else:
            return FoodPairingResult(
                pairings=["cheese", "fruit", "bread", "vegetables"],
                confidence_score=60.0,
                reasoning="Fallback: Universal pairing suggestions"
            )

# Global matcher instance
_matcher_instance = None

def get_wine_matcher() -> GeminiWineMatcher:
    """Get singleton wine matcher instance"""
    global _matcher_instance
    if _matcher_instance is None:
        _matcher_instance = GeminiWineMatcher()
    return _matcher_instance

async def ai_calculate_match_rating(vivino_wine_name: str, systembolaget_wine_name: str,
                                  vivino_rating: float = None, sb_price: float = None,
                                  sb_country: str = None, sb_style: str = None) -> tuple[float, str, str]:
    """
    Calculate wine match using AI
    
    Returns:
        tuple of (confidence_score, match_type, reasoning)
    """
    matcher = get_wine_matcher()
    result = await matcher.match_wines(
        vivino_wine_name, systembolaget_wine_name,
        vivino_rating, sb_price, sb_country, sb_style
    )
    
    return result.confidence_score, result.match_type, result.reasoning

async def ai_simplify_wine_style(wine_style: str) -> WineStyleSimplificationResult:
    """
    Simplify a complex wine style using AI
    
    Args:
        wine_style: Original wine style to simplify
        
    Returns:
        WineStyleSimplificationResult with simplified style
    """
    matcher = get_wine_matcher()
    return await matcher.simplify_wine_style(wine_style)

async def ai_generate_food_pairings(wine_style: str = None, wine_name: str = None, 
                                  country: str = None, grape_varieties: List[str] = None,
                                  body: int = None, acidity: int = None) -> FoodPairingResult:
    """
    Generate simple food pairing suggestions using AI
    
    Args:
        wine_style: Wine style (e.g., "Red Wine", "White Wine")
        wine_name: Name of the wine
        country: Wine country of origin
        grape_varieties: List of grape varieties
        body: Body rating (1-5)
        acidity: Acidity rating (1-5)
        
    Returns:
        FoodPairingResult with simple one-word pairing labels
    """
    matcher = get_wine_matcher()
    return await matcher.generate_food_pairings(wine_style, wine_name, country, grape_varieties, body, acidity)