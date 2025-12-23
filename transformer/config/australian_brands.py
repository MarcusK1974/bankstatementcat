#!/usr/bin/env python3
"""
Comprehensive Australian Brand Database

Curated list of Australian merchants, retailers, and service providers
organized by category for accurate transaction categorization.

Sources:
- Market research on major Australian brands
- Analysis of real transaction data
- Public Australian business directories
"""

# Each entry: (keywords, BASIQ_code, confidence, description)
AUSTRALIAN_BRANDS = [
    
    # ============================================================================
    # SUPERMARKETS & GROCERIES → EXP-016
    # ============================================================================
    (['woolworths', 'woolies'], 'EXP-016', 0.98, 'Woolworths supermarket'),
    (['coles'], 'EXP-016', 0.98, 'Coles supermarket'),
    (['aldi'], 'EXP-016', 0.98, 'ALDI supermarket'),
    (['iga'], 'EXP-016', 0.97, 'IGA supermarket'),
    (['foodworks'], 'EXP-016', 0.97, 'Foodworks supermarket'),
    (['harris farm', 'harris farm markets'], 'EXP-016', 0.97, 'Harris Farm Markets'),
    (['spud shed'], 'EXP-016', 0.96, 'Spud Shed'),
    (['drakes supermarkets', 'drakes'], 'EXP-016', 0.96, 'Drakes Supermarkets'),
    
    # ============================================================================
    # ALCOHOL RETAILERS → EXP-051
    # ============================================================================
    (['dan murphy', 'dan murphys'], 'EXP-051', 0.99, 'Dan Murphy\'s alcohol'),
    (['bws'], 'EXP-051', 0.99, 'BWS alcohol'),
    (['liquorland'], 'EXP-051', 0.98, 'Liquorland'),
    (['first choice liquor', 'first choice'], 'EXP-051', 0.98, 'First Choice Liquor'),
    (['bottle-o', 'bottleo'], 'EXP-051', 0.98, 'Bottle-O'),
    (['vintage cellars'], 'EXP-051', 0.98, 'Vintage Cellars'),
    (['thirsty camel'], 'EXP-051', 0.97, 'Thirsty Camel'),
    
    # ============================================================================
    # FUEL STATIONS → EXP-041
    # ============================================================================
    (['caltex', 'caltex woolworths'], 'EXP-041', 0.98, 'Caltex fuel'),
    (['shell'], 'EXP-041', 0.98, 'Shell fuel'),
    (['bp', 'bp connect'], 'EXP-041', 0.98, 'BP fuel'),
    (['7-eleven', '7 eleven'], 'EXP-041', 0.98, 'Seven Eleven fuel'),
    (['ampol'], 'EXP-041', 0.98, 'Ampol fuel'),
    (['better choice'], 'EXP-041', 0.98, 'Better Choice fuel'),
    (['united petroleum', 'united'], 'EXP-041', 0.97, 'United Petroleum'),
    (['liberty oil'], 'EXP-041', 0.97, 'Liberty Oil'),
    (['metro petroleum'], 'EXP-041', 0.97, 'Metro Petroleum'),
    (['puma energy'], 'EXP-041', 0.97, 'Puma Energy'),
    (['mobil'], 'EXP-041', 0.97, 'Mobil fuel'),
    
    # ============================================================================
    # PUBLIC TRANSPORT → EXP-041
    # ============================================================================
    (['myki'], 'EXP-041', 0.99, 'MYKI public transport (VIC)'),
    (['opal'], 'EXP-041', 0.99, 'Opal card (NSW)'),
    (['go card', 'gocard'], 'EXP-041', 0.99, 'Go Card (QLD)'),
    (['metrocard'], 'EXP-041', 0.99, 'MetroCard (TAS)'),
    (['smartrider'], 'EXP-041', 0.99, 'SmartRider (WA)'),
    (['metrogo'], 'EXP-041', 0.99, 'Metrogo (SA)'),
    
    # ============================================================================
    # PARKING → EXP-041
    # ============================================================================
    (['opark', 'o-park'], 'EXP-041', 0.98, 'OPark parking app'),
    (['wilson parking', 'wilsons'], 'EXP-041', 0.98, 'Wilson Parking'),
    (['secure parking'], 'EXP-041', 0.98, 'Secure Parking'),
    (['care park'], 'EXP-041', 0.97, 'Care Park'),
    
    # ============================================================================
    # TOLLS → EXP-041
    # ============================================================================
    (['linkt'], 'EXP-041', 0.99, 'Linkt toll roads'),
    (['e-tag', 'etag'], 'EXP-041', 0.99, 'E-Tag tolls'),
    
    # ============================================================================
    # FAST FOOD / DINING → EXP-008
    # ============================================================================
    (['mcdonalds', 'mcdonald'], 'EXP-008', 0.99, 'McDonald\'s'),
    (['kfc'], 'EXP-008', 0.99, 'KFC'),
    (['hungry jacks', 'hungry jack'], 'EXP-008', 0.99, 'Hungry Jack\'s'),
    (['red rooster'], 'EXP-008', 0.99, 'Red Rooster'),
    (['oporto'], 'EXP-008', 0.99, 'Oporto'),
    (['guzman y gomez', 'guzman'], 'EXP-008', 0.98, 'Guzman y Gomez'),
    (['nandos', 'nando\'s'], 'EXP-008', 0.98, 'Nando\'s'),
    (['subway'], 'EXP-008', 0.98, 'Subway'),
    (['dominos', 'domino\'s'], 'EXP-008', 0.98, 'Domino\'s Pizza'),
    (['pizza hut'], 'EXP-008', 0.98, 'Pizza Hut'),
    (['crust pizza', 'crust'], 'EXP-008', 0.97, 'Crust Pizza'),
    (['eagle boys'], 'EXP-008', 0.97, 'Eagle Boys Pizza'),
    (['zambrero'], 'EXP-008', 0.97, 'Zambrero'),
    (['roll\'d', 'rolld'], 'EXP-008', 0.97, 'Roll\'d Vietnamese'),
    (['noodle box'], 'EXP-008', 0.97, 'Noodle Box'),
    (['bakers delight'], 'EXP-008', 0.96, 'Bakers Delight'),
    (['boost juice'], 'EXP-008', 0.96, 'Boost Juice'),
    (['gloria jeans', 'gloria jean'], 'EXP-008', 0.96, 'Gloria Jean\'s Coffee'),
    
    # ============================================================================
    # RETAIL / DEPARTMENT STORES → EXP-031 or EXP-007
    # ============================================================================
    (['myer'], 'EXP-007', 0.98, 'Myer department store'),
    (['david jones'], 'EXP-007', 0.98, 'David Jones department store'),
    (['kmart'], 'EXP-031', 0.98, 'Kmart'),
    (['target'], 'EXP-031', 0.98, 'Target'),
    (['big w'], 'EXP-031', 0.98, 'Big W'),
    (['cotton on'], 'EXP-055', 0.97, 'Cotton On clothing'),
    (['jay jays', 'jayjays'], 'EXP-055', 0.97, 'Jay Jays'),
    (['city beach'], 'EXP-055', 0.97, 'City Beach'),
    (['superdry'], 'EXP-055', 0.96, 'Superdry'),
    
    # ============================================================================
    # HOME IMPROVEMENT → EXP-019
    # ============================================================================
    (['bunnings'], 'EXP-019', 0.99, 'Bunnings Warehouse'),
    (['mitre 10'], 'EXP-019', 0.98, 'Mitre 10'),
    (['home timber'], 'EXP-019', 0.98, 'Home Timber & Hardware'),
    (['ikea'], 'EXP-019', 0.97, 'IKEA'),
    (['bcf'], 'EXP-019', 0.96, 'BCF'),
    
    # ============================================================================
    # CHEMIST / PHARMACY → EXP-018
    # ============================================================================
    (['chemist warehouse'], 'EXP-018', 0.99, 'Chemist Warehouse'),
    (['priceline pharmacy', 'priceline'], 'EXP-018', 0.98, 'Priceline'),
    (['terry white', 'terry white chemmart'], 'EXP-018', 0.98, 'Terry White Chemmart'),
    (['amcal'], 'EXP-018', 0.98, 'Amcal'),
    (['blooms the chemist'], 'EXP-018', 0.97, 'Blooms The Chemist'),
    
    # ============================================================================
    # PET SUPPLIES → EXP-028
    # ============================================================================
    (['pet barn', 'petbarn'], 'EXP-028', 0.98, 'Petbarn'),
    (['pet stock', 'petstock'], 'EXP-028', 0.98, 'PETstock'),
    (['budget pet'], 'EXP-028', 0.98, 'Budget Pet Products'),
    (['pet circle'], 'EXP-028', 0.97, 'Pet Circle'),
    
    # ============================================================================
    # GYM & FITNESS → EXP-017
    # ============================================================================
    (['anytime fitness'], 'EXP-017', 0.98, 'Anytime Fitness'),
    (['fitness first'], 'EXP-017', 0.98, 'Fitness First'),
    (['jetts', 'jetts fitness'], 'EXP-017', 0.98, 'Jetts Fitness'),
    (['snap fitness'], 'EXP-017', 0.98, 'Snap Fitness'),
    (['f45'], 'EXP-017', 0.98, 'F45 Training'),
    (['ymca'], 'EXP-017', 0.97, 'YMCA'),
    (['goodlife health'], 'EXP-017', 0.97, 'Goodlife Health Clubs'),
    (['training day gym', 'trainingdaygym'], 'EXP-017', 0.98, 'Training Day Gym'),
    
    # ============================================================================
    # TELECOMMUNICATIONS → EXP-036
    # ============================================================================
    (['telstra'], 'EXP-036', 0.99, 'Telstra'),
    (['optus'], 'EXP-036', 0.99, 'Optus'),
    (['vodafone'], 'EXP-036', 0.99, 'Vodafone'),
    (['tpg'], 'EXP-036', 0.98, 'TPG'),
    (['aussie broadband'], 'EXP-036', 0.98, 'Aussie Broadband'),
    (['iinet'], 'EXP-036', 0.97, 'iiNet'),
    (['dodo'], 'EXP-036', 0.97, 'Dodo'),
    
    # ============================================================================
    # UTILITIES → EXP-040
    # ============================================================================
    (['agl'], 'EXP-040', 0.99, 'AGL Energy'),
    (['origin energy', 'origin'], 'EXP-040', 0.99, 'Origin Energy'),
    (['energy australia', 'energyaustralia'], 'EXP-040', 0.99, 'EnergyAustralia'),
    (['momentum energy'], 'EXP-040', 0.99, 'Momentum Energy'),
    (['red energy'], 'EXP-040', 0.99, 'Red Energy'),
    (['alinta energy'], 'EXP-040', 0.98, 'Alinta Energy'),
    (['simply energy'], 'EXP-040', 0.98, 'Simply Energy'),
    
    # ============================================================================
    # STREAMING / SUBSCRIPTIONS → EXP-035
    # ============================================================================
    (['netflix'], 'EXP-035', 0.99, 'Netflix'),
    (['spotify'], 'EXP-035', 0.99, 'Spotify'),
    (['stan'], 'EXP-035', 0.99, 'Stan'),
    (['disney', 'disney plus', 'disneyplus'], 'EXP-035', 0.99, 'Disney+'),
    (['binge'], 'EXP-035', 0.99, 'Binge'),
    (['kayo'], 'EXP-035', 0.99, 'Kayo Sports'),
    (['amazon prime'], 'EXP-035', 0.98, 'Amazon Prime'),
    (['apple.com/bill', 'apple music'], 'EXP-035', 0.97, 'Apple subscriptions'),
    
    # ============================================================================
    # ONLINE RETAIL → EXP-024
    # ============================================================================
    (['amazon au', 'amazon marketplace', 'amazon reta'], 'EXP-024', 0.99, 'Amazon Australia'),
    (['ebay'], 'EXP-024', 0.98, 'eBay'),
    (['catch.com', 'catch'], 'EXP-024', 0.97, 'Catch.com.au'),
    (['kogan'], 'EXP-024', 0.97, 'Kogan'),
    (['temple and webster', 'temple & webster'], 'EXP-024', 0.96, 'Temple & Webster'),
    (['the iconic'], 'EXP-024', 0.96, 'The Iconic'),
    (['asos'], 'EXP-024', 0.95, 'ASOS'),
    (['shein'], 'EXP-024', 0.95, 'Shein'),
    
    # ============================================================================
    # GAMBLING → EXP-014
    # ============================================================================
    (['tatts', 'tatts online'], 'EXP-014', 0.99, 'Tatts gambling'),
    (['tab'], 'EXP-014', 0.98, 'TAB'),
    (['ladbrokes'], 'EXP-014', 0.98, 'Ladbrokes'),
    (['sportsbet'], 'EXP-014', 0.98, 'Sportsbet'),
    (['bet365'], 'EXP-014', 0.98, 'Bet365'),
    
    # ============================================================================
    # BANKS & FINANCIAL → Various
    # ============================================================================
    (['nab', 'national australia bank'], 'EXP-025', 0.98, 'NAB fees'),
    (['commonwealth bank', 'cba'], 'EXP-025', 0.98, 'CBA fees'),
    (['westpac'], 'EXP-025', 0.98, 'Westpac fees'),
    (['anz'], 'EXP-025', 0.98, 'ANZ fees'),
    
    # ============================================================================
    # RIDE SHARING / DELIVERY → EXP-038 or EXP-008
    # ============================================================================
    (['uber'], 'EXP-038', 0.98, 'Uber ride'),
    (['uber eats'], 'EXP-008', 0.98, 'Uber Eats delivery'),
    (['deliveroo'], 'EXP-008', 0.98, 'Deliveroo'),
    (['menulog'], 'EXP-008', 0.98, 'Menulog'),
    (['doordash'], 'EXP-008', 0.98, 'DoorDash'),
    
    # ============================================================================
    # CHARITIES & DONATIONS → EXP-010
    # ============================================================================
    (['yourtown'], 'EXP-010', 0.98, 'Yourtown charity'),
    (['who gives a crap', 'who gives'], 'EXP-010', 0.97, 'Who Gives A Crap (social enterprise)'),
    
    # ============================================================================
    # OFFICE SUPPLIES → EXP-031
    # ============================================================================
    (['officeworks'], 'EXP-031', 0.99, 'Officeworks'),
    
    # ============================================================================
    # ENTERTAINMENT / MEDIA → EXP-012
    # ============================================================================
    (['event cinemas', 'event'], 'EXP-012', 0.98, 'Event Cinemas'),
    (['hoyts'], 'EXP-012', 0.98, 'Hoyts Cinemas'),
    (['village cinemas'], 'EXP-012', 0.98, 'Village Cinemas'),
    (['reading cinemas', 'readings'], 'EXP-012', 0.98, 'Reading Cinemas'),
    
    # ============================================================================
    # NEWS / PUBLISHING → EXP-035
    # ============================================================================
    (['fairfax', 'fairfax subscriptions'], 'EXP-035', 0.97, 'Fairfax media subscription'),
    (['news corp', 'newscorp'], 'EXP-035', 0.97, 'News Corp subscription'),
    
]

def get_australian_brand_rules():
    """Return list of Australian brand keyword rules for categorization."""
    return AUSTRALIAN_BRANDS


def find_brand_match(description: str) -> tuple[str, float, str] | None:
    """
    Find matching Australian brand in transaction description.
    
    Args:
        description: Transaction description
        
    Returns:
        Tuple of (category, confidence, brand_name) or None if no match
    """
    desc_lower = description.lower()
    
    for keywords, category, confidence, brand_name in AUSTRALIAN_BRANDS:
        if any(kw in desc_lower for kw in keywords):
            return (category, confidence, brand_name)
    
    return None


if __name__ == '__main__':
    # Test the database
    test_descriptions = [
        "WOOLWORTHS/551-557 WARRIGASHWOOD",
        "MYKI HOLMESGLN RS HOL MALVERN EAST",
        "BETTER CHOICE BURWOOD BURWOOD",
        "DAN MURPHY'S/667 WARRIGALCHADSTONE",
        "BUNNINGS 768000 CHADSTONE",
    ]
    
    print("Testing Australian Brand Database:")
    print("="*80)
    for desc in test_descriptions:
        match = find_brand_match(desc)
        if match:
            cat, conf, brand = match
            print(f"✓ {desc[:50]:50s} → {cat} ({brand})")
        else:
            print(f"✗ {desc[:50]:50s} → No match")

