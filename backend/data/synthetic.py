"""
Synthetic data generator for Sentinel MVP.
Creates realistic Kenyan procurement data with embedded fraud patterns.
"""

from datetime import date, datetime, timedelta
from models import (
    Tender, Company, Director, PublicOfficial, Bid,
    TenderStatus, RelationshipType
)


def generate_synthetic_data() -> dict:
    """
    Generate a complete synthetic dataset with embedded fraud patterns.
    
    Patterns included:
    1. Wanjiku Construction Cartel - 4 companies that bid together, rotating wins
    2. Shell Company Scheme - FastTrack Solutions registered 4 days before winning
    3. Conflict of Interest - HealthFirst director is brother of KEMSA procurement officer
    4. Price Inflation - Medical supplies at 180% market rate
    5. Rushed Timeline - IT tender with 5-day window
    """
    
    # Directors
    directors = [
        # Cartel directors (some overlap)
        Director(id="dir-001", name="Peter Wanjiku Kamau", company_ids=["comp-001", "comp-002"]),
        Director(id="dir-002", name="Grace Njeri Wanjiku", company_ids=["comp-001"]),
        Director(id="dir-003", name="Samuel Ochieng Otieno", company_ids=["comp-002", "comp-003"]),
        Director(id="dir-004", name="Mary Akinyi Ouma", company_ids=["comp-003"]),
        Director(id="dir-005", name="David Kipchoge Ruto", company_ids=["comp-004"]),
        Director(id="dir-006", name="Elizabeth Wambui Kariuki", company_ids=["comp-004"]),
        
        # Shell company director
        Director(id="dir-007", name="Michael Otieno Odhiambo", company_ids=["comp-005"]),
        
        # Conflict of interest director (brother of official)
        Director(id="dir-008", name="John Kamau Mwangi", company_ids=["comp-006"]),
        Director(id="dir-009", name="Anne Wanjiru Mwangi", company_ids=["comp-006"]),
        
        # Clean companies directors
        Director(id="dir-010", name="Francis Mutua Kilonzo", company_ids=["comp-007"]),
        Director(id="dir-011", name="Catherine Nyambura Gitau", company_ids=["comp-008"]),
        Director(id="dir-012", name="Patrick Kiprotich Korir", company_ids=["comp-009"]),
        Director(id="dir-013", name="Susan Adhiambo Achieng", company_ids=["comp-010"]),
        Director(id="dir-014", name="Joseph Mwenda Nthiga", company_ids=["comp-011"]),
        Director(id="dir-015", name="Margaret Wairimu Ndung'u", company_ids=["comp-012"]),
    ]
    
    # Public Officials
    officials = [
        PublicOfficial(
            id="off-001",
            name="James Mwangi Kamau",  # Brother of dir-008
            department="Kenya Medical Supplies Authority",
            position="Chief Procurement Officer",
            related_persons={"dir-008": RelationshipType.SIBLING}
        ),
        PublicOfficial(
            id="off-002",
            name="Alice Chebet Kiptoo",
            department="Kenya Rural Roads Authority",
            position="Procurement Manager",
            related_persons={}
        ),
        PublicOfficial(
            id="off-003",
            name="Robert Omondi Onyango",
            department="Ministry of Health",
            position="Senior Procurement Officer",
            related_persons={}
        ),
        PublicOfficial(
            id="off-004",
            name="Janet Wangui Muturi",
            department="Kenya Power and Lighting Company",
            position="Head of Procurement",
            related_persons={}
        ),
        PublicOfficial(
            id="off-005",
            name="Daniel Rotich Kibet",
            department="Nakuru County Government",
            position="County Procurement Director",
            related_persons={}
        ),
    ]
    
    # Companies
    companies = [
        # Cartel companies (share address variations)
        Company(
            id="comp-001",
            name="Wanjiku Construction Ltd",
            registration_number="PVT-2019-045678",
            registration_date=date(2019, 3, 15),
            address="Plot 45, Industrial Area, Nairobi",
            phone="+254 20 555 0001",
            director_ids=["dir-001", "dir-002"]
        ),
        Company(
            id="comp-002",
            name="Mwamba Developers Co.",
            registration_number="PVT-2018-034521",
            registration_date=date(2018, 7, 22),
            address="Plot 45A, Industrial Area, Nairobi",  # Same plot
            phone="+254 20 555 0002",
            director_ids=["dir-001", "dir-003"]  # Peter Wanjiku is in both
        ),
        Company(
            id="comp-003",
            name="Safari Contractors Ltd",
            registration_number="PVT-2020-067890",
            registration_date=date(2020, 1, 10),
            address="Plot 47, Industrial Area, Nairobi",  # Adjacent plot
            phone="+254 20 555 0003",
            director_ids=["dir-003", "dir-004"]  # Samuel Ochieng is in both
        ),
        Company(
            id="comp-004",
            name="Eastlands Builders Ltd",
            registration_number="PVT-2017-012345",
            registration_date=date(2017, 11, 5),
            address="Plot 45B, Industrial Area, Nairobi",  # Same plot variation
            phone="+254 20 555 0001",  # Same phone as Wanjiku!
            director_ids=["dir-005", "dir-006"]
        ),
        
        # Shell company (registered very recently)
        Company(
            id="comp-005",
            name="FastTrack Solutions Ltd",
            registration_number="PVT-2026-000123",
            registration_date=date(2026, 1, 11),  # Just 4 days before tender win
            address="Virtual Office, Westlands, Nairobi",
            phone="+254 700 123 456",
            director_ids=["dir-007"]
        ),
        
        # Conflict of interest company
        Company(
            id="comp-006",
            name="HealthFirst Medical Supplies Ltd",
            registration_number="PVT-2021-078901",
            registration_date=date(2021, 5, 18),
            address="Likoni Road, Industrial Area, Nairobi",
            phone="+254 20 444 5678",
            director_ids=["dir-008", "dir-009"]  # John Mwangi is brother of KEMSA officer
        ),
        
        # Clean companies
        Company(
            id="comp-007",
            name="Kilonzo Office Supplies",
            registration_number="PVT-2015-023456",
            registration_date=date(2015, 8, 12),
            address="Mombasa Road, Nairobi",
            phone="+254 20 333 4567",
            director_ids=["dir-010"]
        ),
        Company(
            id="comp-008",
            name="Gitau Medical Equipment Ltd",
            registration_number="PVT-2016-034567",
            registration_date=date(2016, 2, 28),
            address="Upper Hill, Nairobi",
            phone="+254 20 222 3456",
            director_ids=["dir-011"]
        ),
        Company(
            id="comp-009",
            name="Korir Road Construction Co.",
            registration_number="PVT-2014-045678",
            registration_date=date(2014, 6, 15),
            address="Eldoret Town, Uasin Gishu",
            phone="+254 53 206 1234",
            director_ids=["dir-012"]
        ),
        Company(
            id="comp-010",
            name="Achieng IT Solutions",
            registration_number="PVT-2019-056789",
            registration_date=date(2019, 9, 3),
            address="Kisumu CBD, Kisumu",
            phone="+254 57 202 5678",
            director_ids=["dir-013"]
        ),
        Company(
            id="comp-011",
            name="Nthiga Security Services",
            registration_number="PVT-2018-067890",
            registration_date=date(2018, 4, 20),
            address="Meru Town, Meru",
            phone="+254 64 203 1234",
            director_ids=["dir-014"]
        ),
        Company(
            id="comp-012",
            name="Ndung'u Pharmaceuticals Ltd",
            registration_number="PVT-2012-078901",
            registration_date=date(2012, 11, 8),
            address="Thika Road, Nairobi",
            phone="+254 20 876 5432",
            director_ids=["dir-015"]
        ),
    ]
    
    # Tenders
    tenders = [
        # HIGH RISK: Cartel tender #1 - Road construction with cartel bidding
        Tender(
            id="tender-001",
            reference_number="KURA/NCB/2026/001",
            title="Construction of Nairobi-Nakuru Highway Section B",
            description="Construction and maintenance of 25km highway section including drainage and signage",
            procuring_entity="Kenya Rural Roads Authority",
            category="Road Construction",
            estimated_value=450_000_000,  # KES 450M
            published_date=date(2026, 1, 2),
            deadline=date(2026, 1, 16),
            status=TenderStatus.AWARDED,
            awarded_to="comp-001",  # Wanjiku Construction
            awarded_amount=445_000_000,
            procurement_officer_id="off-002"
        ),
        
        # HIGH RISK: Shell company tender
        Tender(
            id="tender-002",
            reference_number="KPLC/IT/2026/002",
            title="Enterprise IT Infrastructure Modernization",
            description="Supply and installation of data center equipment and network infrastructure",
            procuring_entity="Kenya Power and Lighting Company",
            category="Information Technology",
            estimated_value=78_000_000,
            published_date=date(2026, 1, 10),
            deadline=date(2026, 1, 15),  # Only 5 days! Rushed timeline
            status=TenderStatus.AWARDED,
            awarded_to="comp-005",  # FastTrack - shell company
            awarded_amount=78_000_000,
            procurement_officer_id="off-004"
        ),
        
        # HIGH RISK: Conflict of interest tender
        Tender(
            id="tender-003",
            reference_number="KEMSA/MED/2026/003",
            title="Supply of Essential Medical Equipment",
            description="Supply of diagnostic equipment, patient monitors, and surgical instruments to Level 5 hospitals",
            procuring_entity="Kenya Medical Supplies Authority",
            category="Medical Supplies",
            estimated_value=120_000_000,
            published_date=date(2026, 1, 5),
            deadline=date(2026, 1, 19),
            status=TenderStatus.AWARDED,
            awarded_to="comp-006",  # HealthFirst - director is brother of procurement officer
            awarded_amount=118_500_000,
            procurement_officer_id="off-001"  # James Mwangi - brother of John Mwangi
        ),
        
        # MEDIUM RISK: Cartel tender #2 - Different winner from same cartel
        Tender(
            id="tender-004",
            reference_number="NCG/ROADS/2026/004",
            title="Nakuru Town Roads Rehabilitation",
            description="Rehabilitation of 15km urban roads including footpaths and street lighting",
            procuring_entity="Nakuru County Government",
            category="Road Construction",
            estimated_value=85_000_000,
            published_date=date(2026, 1, 3),
            deadline=date(2026, 1, 17),
            status=TenderStatus.AWARDED,
            awarded_to="comp-003",  # Safari Contractors - cartel member
            awarded_amount=82_000_000,
            procurement_officer_id="off-005"
        ),
        
        # HIGH RISK: Price anomaly tender
        Tender(
            id="tender-005",
            reference_number="MOH/SUPP/2026/005",
            title="Supply of Pharmaceutical Products Q1 2026",
            description="Supply of essential medicines and pharmaceutical products to public health facilities",
            procuring_entity="Ministry of Health",
            category="Medical Supplies",
            estimated_value=45_000_000,  # Estimated at 45M
            published_date=date(2026, 1, 8),
            deadline=date(2026, 1, 22),
            status=TenderStatus.AWARDED,
            awarded_to="comp-006",  # HealthFirst again - price inflated
            awarded_amount=81_000_000,  # 180% of estimate!
            procurement_officer_id="off-003"
        ),
        
        # LOW RISK: Clean tender
        Tender(
            id="tender-006",
            reference_number="MOH/EQUIP/2026/006",
            title="Office Equipment and Furniture Supply",
            description="Supply of office furniture, computers, and equipment for new MoH annexe",
            procuring_entity="Ministry of Health",
            category="Office Supplies",
            estimated_value=8_500_000,
            published_date=date(2026, 1, 4),
            deadline=date(2026, 1, 25),
            status=TenderStatus.AWARDED,
            awarded_to="comp-007",  # Kilonzo Office Supplies - clean
            awarded_amount=8_200_000,
            procurement_officer_id="off-003"
        ),
        
        # LOW RISK: Clean tender
        Tender(
            id="tender-007",
            reference_number="UG/ROADS/2026/007",
            title="Eldoret-Iten Road Maintenance",
            description="Routine maintenance and pothole repair for 40km section",
            procuring_entity="Kenya Rural Roads Authority",
            category="Road Construction",
            estimated_value=25_000_000,
            published_date=date(2026, 1, 6),
            deadline=date(2026, 1, 27),
            status=TenderStatus.AWARDED,
            awarded_to="comp-009",  # Korir Road Construction - clean, local
            awarded_amount=24_500_000,
            procurement_officer_id="off-002"
        ),
        
        # MEDIUM RISK: Cartel tender #3
        Tender(
            id="tender-008",
            reference_number="KURA/NCB/2026/008",
            title="Mombasa Road Expansion Project Phase 1",
            description="Expansion of Mombasa Road from 4 to 6 lanes, 10km section",
            procuring_entity="Kenya Rural Roads Authority",
            category="Road Construction",
            estimated_value=320_000_000,
            published_date=date(2026, 1, 7),
            deadline=date(2026, 1, 21),
            status=TenderStatus.EVALUATION,
            awarded_to=None,
            awarded_amount=None,
            procurement_officer_id="off-002"
        ),
        
        # LOW RISK: Pending tender
        Tender(
            id="tender-009",
            reference_number="KIS/IT/2026/009",
            title="Kisumu County Digital Services Platform",
            description="Development and deployment of e-government platform for county services",
            procuring_entity="Kisumu County Government",
            category="Information Technology",
            estimated_value=35_000_000,
            published_date=date(2026, 1, 10),
            deadline=date(2026, 1, 31),
            status=TenderStatus.OPEN,
            awarded_to=None,
            awarded_amount=None,
            procurement_officer_id=None
        ),
        
        # LOW RISK: Clean medical tender
        Tender(
            id="tender-010",
            reference_number="KEMSA/MED/2026/010",
            title="Supply of Laboratory Reagents",
            description="Supply of laboratory reagents and consumables to national reference laboratories",
            procuring_entity="Kenya Medical Supplies Authority",
            category="Medical Supplies",
            estimated_value=28_000_000,
            published_date=date(2026, 1, 9),
            deadline=date(2026, 1, 30),
            status=TenderStatus.AWARDED,
            awarded_to="comp-012",  # Ndung'u Pharmaceuticals - clean, established
            awarded_amount=27_200_000,
            procurement_officer_id="off-001"
        ),
        
        # MEDIUM RISK: Another cartel tender
        Tender(
            id="tender-011",
            reference_number="NCG/BUILD/2026/011",
            title="Construction of Nakuru Level 4 Hospital Extension",
            description="Construction of new wing including emergency unit and ICU facilities",
            procuring_entity="Nakuru County Government",
            category="Building Construction",
            estimated_value=180_000_000,
            published_date=date(2026, 1, 8),
            deadline=date(2026, 1, 22),
            status=TenderStatus.AWARDED,
            awarded_to="comp-002",  # Mwamba Developers - cartel member
            awarded_amount=175_000_000,
            procurement_officer_id="off-005"
        ),
        
        # LOW RISK: Security services
        Tender(
            id="tender-012",
            reference_number="MOH/SEC/2026/012",
            title="Security Services for MoH Facilities",
            description="Provision of security guard services for Ministry headquarters and regional offices",
            procuring_entity="Ministry of Health",
            category="Security Services",
            estimated_value=12_000_000,  # Annual contract
            published_date=date(2026, 1, 11),
            deadline=date(2026, 2, 1),
            status=TenderStatus.OPEN,
            awarded_to=None,
            awarded_amount=None,
            procurement_officer_id="off-003"
        ),
        
        # LOW RISK: IT services
        Tender(
            id="tender-013",
            reference_number="KPLC/IT/2026/013",
            title="Annual IT Support and Maintenance",
            description="Provision of IT support services for Kenya Power regional offices",
            procuring_entity="Kenya Power and Lighting Company",
            category="Information Technology",
            estimated_value=18_000_000,
            published_date=date(2026, 1, 12),
            deadline=date(2026, 2, 5),
            status=TenderStatus.OPEN,
            awarded_to=None,
            awarded_amount=None,
            procurement_officer_id="off-004"
        ),
        
        # MEDIUM RISK: Rushed timeline
        Tender(
            id="tender-014",
            reference_number="KEMSA/EMG/2026/014",
            title="Emergency Medical Supplies Procurement",
            description="Emergency procurement of PPE and medical consumables",
            procuring_entity="Kenya Medical Supplies Authority",
            category="Medical Supplies",
            estimated_value=55_000_000,
            published_date=date(2026, 1, 14),
            deadline=date(2026, 1, 18),  # Only 4 days - rushed
            status=TenderStatus.EVALUATION,
            awarded_to=None,
            awarded_amount=None,
            procurement_officer_id="off-001"
        ),
        
        # MEDIUM RISK: Cartel tender #4
        Tender(
            id="tender-015",
            reference_number="KURA/NCB/2026/015",
            title="Thika Superhighway Repairs",
            description="Emergency repairs and resurfacing of damaged sections",
            procuring_entity="Kenya Rural Roads Authority",
            category="Road Construction",
            estimated_value=95_000_000,
            published_date=date(2026, 1, 5),
            deadline=date(2026, 1, 19),
            status=TenderStatus.AWARDED,
            awarded_to="comp-004",  # Eastlands Builders - cartel member
            awarded_amount=93_000_000,
            procurement_officer_id="off-002"
        ),
        
        # LOW RISK: Clean office tender
        Tender(
            id="tender-016",
            reference_number="KIS/SUP/2026/016",
            title="Office Stationery and Supplies",
            description="Annual framework contract for office stationery and consumables",
            procuring_entity="Kisumu County Government",
            category="Office Supplies",
            estimated_value=4_500_000,
            published_date=date(2026, 1, 13),
            deadline=date(2026, 2, 10),
            status=TenderStatus.OPEN,
            awarded_to=None,
            awarded_amount=None,
            procurement_officer_id=None
        ),
        
        # LOW RISK: Medical equipment
        Tender(
            id="tender-017",
            reference_number="MOH/EQUIP/2026/017",
            title="Dialysis Machines for Level 5 Hospitals",
            description="Supply and installation of 50 dialysis machines with training",
            procuring_entity="Ministry of Health",
            category="Medical Supplies",
            estimated_value=150_000_000,
            published_date=date(2026, 1, 6),
            deadline=date(2026, 1, 27),
            status=TenderStatus.AWARDED,
            awarded_to="comp-008",  # Gitau Medical - clean, specialized
            awarded_amount=148_000_000,
            procurement_officer_id="off-003"
        ),
        
        # CANCELLED tender
        Tender(
            id="tender-018",
            reference_number="NCG/IT/2026/018",
            title="County Revenue Collection System",
            description="Development of integrated revenue collection and management system",
            procuring_entity="Nakuru County Government",
            category="Information Technology",
            estimated_value=42_000_000,
            published_date=date(2026, 1, 4),
            deadline=date(2026, 1, 18),
            status=TenderStatus.CANCELLED,
            awarded_to=None,
            awarded_amount=None,
            procurement_officer_id="off-005"
        ),
        
        # LOW RISK: Road maintenance
        Tender(
            id="tender-019",
            reference_number="KURA/MAINT/2026/019",
            title="Routine Road Maintenance - Western Region",
            description="Annual routine maintenance contract for classified roads in Western Kenya",
            procuring_entity="Kenya Rural Roads Authority",
            category="Road Construction",
            estimated_value=65_000_000,
            published_date=date(2026, 1, 10),
            deadline=date(2026, 2, 3),
            status=TenderStatus.EVALUATION,
            awarded_to=None,
            awarded_amount=None,
            procurement_officer_id="off-002"
        ),
        
        # LOW RISK: Clean tender
        Tender(
            id="tender-020",
            reference_number="KPLC/SEC/2026/020",
            title="Security Systems Upgrade",
            description="Supply and installation of CCTV and access control systems",
            procuring_entity="Kenya Power and Lighting Company",
            category="Security Services",
            estimated_value=22_000_000,
            published_date=date(2026, 1, 11),
            deadline=date(2026, 2, 4),
            status=TenderStatus.OPEN,
            awarded_to=None,
            awarded_amount=None,
            procurement_officer_id="off-004"
        ),
    ]
    
    # Bids
    bids = [
        # Tender 001 - Cartel bidding pattern (all 4 cartel members bid)
        Bid(id="bid-001", tender_id="tender-001", company_id="comp-001", amount=445_000_000, submission_date=datetime(2026, 1, 16, 14, 30)),
        Bid(id="bid-002", tender_id="tender-001", company_id="comp-002", amount=448_000_000, submission_date=datetime(2026, 1, 16, 14, 45)),
        Bid(id="bid-003", tender_id="tender-001", company_id="comp-003", amount=452_000_000, submission_date=datetime(2026, 1, 16, 15, 00)),
        Bid(id="bid-004", tender_id="tender-001", company_id="comp-004", amount=455_000_000, submission_date=datetime(2026, 1, 16, 15, 15)),
        Bid(id="bid-005", tender_id="tender-001", company_id="comp-009", amount=460_000_000, submission_date=datetime(2026, 1, 15, 10, 00)),
        
        # Tender 002 - Shell company wins (only bidder with capacity)
        Bid(id="bid-006", tender_id="tender-002", company_id="comp-005", amount=78_000_000, submission_date=datetime(2026, 1, 15, 11, 55)),  # Last minute
        Bid(id="bid-007", tender_id="tender-002", company_id="comp-010", amount=82_000_000, submission_date=datetime(2026, 1, 14, 9, 00)),
        
        # Tender 003 - Conflict of interest
        Bid(id="bid-008", tender_id="tender-003", company_id="comp-006", amount=118_500_000, submission_date=datetime(2026, 1, 19, 10, 00)),
        Bid(id="bid-009", tender_id="tender-003", company_id="comp-008", amount=125_000_000, submission_date=datetime(2026, 1, 18, 14, 00)),
        Bid(id="bid-010", tender_id="tender-003", company_id="comp-012", amount=122_000_000, submission_date=datetime(2026, 1, 18, 16, 30)),
        
        # Tender 004 - Cartel pattern continues
        Bid(id="bid-011", tender_id="tender-004", company_id="comp-001", amount=84_000_000, submission_date=datetime(2026, 1, 17, 9, 00)),
        Bid(id="bid-012", tender_id="tender-004", company_id="comp-002", amount=85_000_000, submission_date=datetime(2026, 1, 17, 9, 30)),
        Bid(id="bid-013", tender_id="tender-004", company_id="comp-003", amount=82_000_000, submission_date=datetime(2026, 1, 17, 10, 00)),  # Winner
        Bid(id="bid-014", tender_id="tender-004", company_id="comp-004", amount=86_000_000, submission_date=datetime(2026, 1, 17, 10, 30)),
        
        # Tender 005 - Price inflation (HealthFirst wins at inflated price)
        Bid(id="bid-015", tender_id="tender-005", company_id="comp-006", amount=81_000_000, submission_date=datetime(2026, 1, 22, 11, 00)),  # 180% of estimate
        Bid(id="bid-016", tender_id="tender-005", company_id="comp-012", amount=48_000_000, submission_date=datetime(2026, 1, 21, 14, 00)),  # Reasonable
        
        # Tender 006 - Clean tender
        Bid(id="bid-017", tender_id="tender-006", company_id="comp-007", amount=8_200_000, submission_date=datetime(2026, 1, 24, 10, 00)),
        Bid(id="bid-018", tender_id="tender-006", company_id="comp-010", amount=8_800_000, submission_date=datetime(2026, 1, 23, 15, 00)),
        
        # Tender 007 - Clean local tender
        Bid(id="bid-019", tender_id="tender-007", company_id="comp-009", amount=24_500_000, submission_date=datetime(2026, 1, 26, 11, 00)),
        
        # Tender 008 - Evaluation phase (cartel bidding again)
        Bid(id="bid-020", tender_id="tender-008", company_id="comp-001", amount=318_000_000, submission_date=datetime(2026, 1, 21, 14, 00)),
        Bid(id="bid-021", tender_id="tender-008", company_id="comp-002", amount=315_000_000, submission_date=datetime(2026, 1, 21, 14, 30)),
        Bid(id="bid-022", tender_id="tender-008", company_id="comp-003", amount=322_000_000, submission_date=datetime(2026, 1, 21, 15, 00)),
        Bid(id="bid-023", tender_id="tender-008", company_id="comp-004", amount=325_000_000, submission_date=datetime(2026, 1, 21, 15, 30)),
        
        # Tender 010 - Clean pharmaceutical
        Bid(id="bid-024", tender_id="tender-010", company_id="comp-012", amount=27_200_000, submission_date=datetime(2026, 1, 29, 10, 00)),
        Bid(id="bid-025", tender_id="tender-010", company_id="comp-006", amount=29_000_000, submission_date=datetime(2026, 1, 29, 11, 00)),
        
        # Tender 011 - Cartel building tender
        Bid(id="bid-026", tender_id="tender-011", company_id="comp-001", amount=178_000_000, submission_date=datetime(2026, 1, 22, 9, 00)),
        Bid(id="bid-027", tender_id="tender-011", company_id="comp-002", amount=175_000_000, submission_date=datetime(2026, 1, 22, 9, 30)),  # Winner
        Bid(id="bid-028", tender_id="tender-011", company_id="comp-003", amount=182_000_000, submission_date=datetime(2026, 1, 22, 10, 00)),
        Bid(id="bid-029", tender_id="tender-011", company_id="comp-004", amount=185_000_000, submission_date=datetime(2026, 1, 22, 10, 30)),
        
        # Tender 014 - Emergency procurement (rushed)
        Bid(id="bid-030", tender_id="tender-014", company_id="comp-006", amount=54_000_000, submission_date=datetime(2026, 1, 18, 11, 00)),
        Bid(id="bid-031", tender_id="tender-014", company_id="comp-012", amount=52_000_000, submission_date=datetime(2026, 1, 17, 16, 00)),
        
        # Tender 015 - Cartel road tender
        Bid(id="bid-032", tender_id="tender-015", company_id="comp-001", amount=94_000_000, submission_date=datetime(2026, 1, 19, 10, 00)),
        Bid(id="bid-033", tender_id="tender-015", company_id="comp-002", amount=96_000_000, submission_date=datetime(2026, 1, 19, 10, 30)),
        Bid(id="bid-034", tender_id="tender-015", company_id="comp-003", amount=97_000_000, submission_date=datetime(2026, 1, 19, 11, 00)),
        Bid(id="bid-035", tender_id="tender-015", company_id="comp-004", amount=93_000_000, submission_date=datetime(2026, 1, 19, 11, 30)),  # Winner
        
        # Tender 017 - Clean medical equipment
        Bid(id="bid-036", tender_id="tender-017", company_id="comp-008", amount=148_000_000, submission_date=datetime(2026, 1, 26, 14, 00)),
        Bid(id="bid-037", tender_id="tender-017", company_id="comp-006", amount=155_000_000, submission_date=datetime(2026, 1, 26, 15, 00)),
        
        # Tender 019 - Evaluation phase
        Bid(id="bid-038", tender_id="tender-019", company_id="comp-009", amount=63_000_000, submission_date=datetime(2026, 2, 2, 10, 00)),
        Bid(id="bid-039", tender_id="tender-019", company_id="comp-001", amount=64_000_000, submission_date=datetime(2026, 2, 2, 11, 00)),
    ]
    
    return {
        "directors": directors,
        "officials": officials,
        "companies": companies,
        "tenders": tenders,
        "bids": bids,
    }


# Convenience function to get data as dictionaries for easy lookup
def get_data_store():
    """Returns data organized for efficient lookup."""
    data = generate_synthetic_data()
    
    return {
        "directors": {d.id: d for d in data["directors"]},
        "officials": {o.id: o for o in data["officials"]},
        "companies": {c.id: c for c in data["companies"]},
        "tenders": {t.id: t for t in data["tenders"]},
        "bids": data["bids"],
        "bids_by_tender": _group_bids_by_tender(data["bids"]),
    }


def _group_bids_by_tender(bids: list[Bid]) -> dict[str, list[Bid]]:
    """Group bids by tender ID."""
    result = {}
    for bid in bids:
        if bid.tender_id not in result:
            result[bid.tender_id] = []
        result[bid.tender_id].append(bid)
    return result
