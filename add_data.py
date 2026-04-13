import os
import django
import csv
from decimal import Decimal, InvalidOperation
from datetime import datetime
from django.utils import timezone

# 1. Properly Django setup
# Hyphenated directory 'E-Commerce' is handled by setting DJANGO_SETTINGS_MODULE
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'E-Commerce.settings')
django.setup()

# 2. Import model correctly
from store.models import Product
from accounts.models import CustomUser

# 3. Product data: list named PRODUCT_DATA
PRODUCT_DATA = [
  {
    "Company name (purchased from)": "FACT LTD",
    "Company GSTIN": "29AAACT6204C1ZP",
    "Purchase date": "12.02.2026",
    "Purchase invoice number": "KA0031919369",
    "Product name": "FACT DAP",
    "Category": "FERTILIZER",
    "GST (%)": 5,
    "HSN": "31053000",
    "Batch no.": "---",
    "Quantity (total number)": 140,
    "Measurement type": "KG",
    "Unit Capacity (weight/volume)": 50,
    "Taxable Unit Amount": 1258.7,
    "Taxable Total Amount": 176218,
    "Total Amount (Incl. GST)": 185028.9
  },
  {
    "Company name (purchased from)": "FACT LTD",
    "Company GSTIN": "29AAACT6204C1ZP",
    "Purchase date": "12.02.2026",
    "Purchase invoice number": "KA0031919370",
    "Product name": "FACT TSP",
    "Category": "FERTILIZER",
    "GST (%)": 5,
    "HSN": "31031100",
    "Batch no.": "---",
    "Quantity (total number)": 80,
    "Measurement type": "KG",
    "Unit Capacity (weight/volume)": 50,
    "Taxable Unit Amount": 1186.1,
    "Taxable Total Amount": 94888,
    "Total Amount (Incl. GST)": 99632.4
  },
  {
    "Company name (purchased from)": "RATHODE FERTLIZERS",
    "Company GSTIN": "29AAGFR3368E1ZO",
    "Purchase date": "26.03.2026",
    "Purchase invoice number": "AI/230",
    "Product name": "GROMER 16.20.00.13",
    "Category": "FERTILIZER",
    "GST (%)": 5,
    "HSN": "31053000",
    "Batch no.": "---",
    "Quantity (total number)": 200,
    "Measurement type": "KG",
    "Unit Capacity (weight/volume)": 50,
    "Taxable Unit Amount": 1366.67,
    "Taxable Total Amount": 273334,
    "Total Amount (Incl. GST)": 287000.7
  },
  {
    "Company name (purchased from)": "RATHODE FERTLIZERS",
    "Company GSTIN": "29AAGFR3368E1ZO",
    "Purchase date": "26.03.2026",
    "Purchase invoice number": "AI/230",
    "Product name": "GROMER 20.20.00.13",
    "Category": "FERTILIZER",
    "GST (%)": 5,
    "HSN": "31055100",
    "Batch no.": "---",
    "Quantity (total number)": 200,
    "Measurement type": "KG",
    "Unit Capacity (weight/volume)": 50,
    "Taxable Unit Amount": 1414.29,
    "Taxable Total Amount": 282858,
    "Total Amount (Incl. GST)": 297000.9
  },
  {
    "Company name (purchased from)": "RATHODE FERTLIZERS",
    "Company GSTIN": "29AAGFR3368E1ZO",
    "Purchase date": "12.12.2026",
    "Purchase invoice number": "AI/104",
    "Product name": "PPL 10.26.26",
    "Category": "FERTILIZER",
    "GST (%)": 5,
    "HSN": "31052000",
    "Batch no.": "---",
    "Quantity (total number)": 42,
    "Measurement type": "KG",
    "Unit Capacity (weight/volume)": 50,
    "Taxable Unit Amount": 1885.71,
    "Taxable Total Amount": 79199.82,
    "Total Amount (Incl. GST)": 83159.811
  },
  {
    "Company name (purchased from)": "FACT LTD",
    "Company GSTIN": "29AAACT6204C1ZP",
    "Purchase date": "06.03.2026",
    "Purchase invoice number": "KA0031920326",
    "Product name": "FACT 20.20.00.13",
    "Category": "FERTILIZER",
    "GST (%)": 5,
    "HSN": "31054000",
    "Batch no.": "---",
    "Quantity (total number)": 50,
    "Measurement type": "KG",
    "Unit Capacity (weight/volume)": 50,
    "Taxable Unit Amount": 1310.75,
    "Taxable Total Amount": 65537.5,
    "Total Amount (Incl. GST)": 68814.375
  },
  {
    "Company name (purchased from)": "J S BELLAD AND BROTHERS",
    "Company GSTIN": "29AALFJ8928K1ZI",
    "Purchase date": "21.01.2026",
    "Purchase invoice number": "JSB/W/2777",
    "Product name": "KISAN SAGARARATN",
    "Category": "SEAWEED GR",
    "GST (%)": 5,
    "HSN": "31010099",
    "Batch no.": "---",
    "Quantity (total number)": 60,
    "Measurement type": "KG",
    "Unit Capacity (weight/volume)": 10,
    "Taxable Unit Amount": 400,
    "Taxable Total Amount": 24000,
    "Total Amount (Incl. GST)": 25200
  },
  {
    "Company name (purchased from)": "J S BELLAD AND BROTHERS",
    "Company GSTIN": "29AALFJ8928K1ZI",
    "Purchase date": "21.01.2026",
    "Purchase invoice number": "JSB/W/2777",
    "Product name": "UREA",
    "Category": "FERTILIZER",
    "GST (%)": 5,
    "HSN": "31021000",
    "Batch no.": "---",
    "Quantity (total number)": 450,
    "Measurement type": "KG",
    "Unit Capacity (weight/volume)": 50,
    "Taxable Unit Amount": 238.1,
    "Taxable Total Amount": 107145,
    "Total Amount (Incl. GST)": 112502.25
  },
  {
    "Company name (purchased from)": "FACT LTD",
    "Company GSTIN": "29AAACT6204C1ZP",
    "Purchase date": "21.03.2026",
    "Purchase invoice number": "KA0031920940",
    "Product name": "15.15.15",
    "Category": "FERTILIZER",
    "GST (%)": 5,
    "HSN": "31052000",
    "Batch no.": "---",
    "Quantity (total number)": 20,
    "Measurement type": "KG",
    "Unit Capacity (weight/volume)": 50,
    "Taxable Unit Amount": 1467.95,
    "Taxable Total Amount": 29359,
    "Total Amount (Incl. GST)": 30826.95
  },
  {
    "Company name (purchased from)": "KR LIFE SCIENCE PVT LTD",
    "Company GSTIN": "29AAICK5339B1ZI",
    "Purchase date": "23.03.2026",
    "Purchase invoice number": "111/P/2526/10439",
    "Product name": "TARZEN RITE",
    "Category": "INSECTICIDE",
    "GST (%)": 18,
    "HSN": "38089199",
    "Batch no.": "KRK079",
    "Quantity (total number)": 33,
    "Measurement type": "KG",
    "Unit Capacity (weight/volume)": 4,
    "Taxable Unit Amount": 312.264,
    "Taxable Total Amount": 10304.712,
    "Total Amount (Incl. GST)": 12159.56016
  },
  {
    "Company name (purchased from)": "KR LIFE SCIENCE PVT LTD",
    "Company GSTIN": "29AAICK5339B1ZI",
    "Purchase date": "23.03.2026",
    "Purchase invoice number": "111/P/2526/10439",
    "Product name": "TRICKY",
    "Category": "FUNGUSIDE",
    "GST (%)": 18,
    "HSN": "38089290",
    "Batch no.": "KRR0406",
    "Quantity (total number)": 53,
    "Measurement type": "GM",
    "Unit Capacity (weight/volume)": 120,
    "Taxable Unit Amount": 107.217,
    "Taxable Total Amount": 5682.501,
    "Total Amount (Incl. GST)": 6705.35118
  },
  {
    "Company name (purchased from)": "KR LIFE SCIENCE PVT LTD",
    "Company GSTIN": "29AAICK5339B1ZI",
    "Purchase date": "23.03.2026",
    "Purchase invoice number": "111/P/2526/05039",
    "Product name": "ZINDAN",
    "Category": "ZnO",
    "GST (%)": 5,
    "HSN": "28170010",
    "Batch no.": "KRKMNZ006",
    "Quantity (total number)": 2,
    "Measurement type": "LTR",
    "Unit Capacity (weight/volume)": 1,
    "Taxable Unit Amount": 775.917,
    "Taxable Total Amount": 1551.834,
    "Total Amount (Incl. GST)": 1629.4257
  },
  {
    "Company name (purchased from)": "KR LIFE SCIENCE PVT LTD",
    "Company GSTIN": "29AAICK5339B1ZI",
    "Purchase date": "23.03.2026",
    "Purchase invoice number": "111/P/2526/05039",
    "Product name": "ZINDAN",
    "Category": "ZnO",
    "GST (%)": 5,
    "HSN": "28170010",
    "Batch no.": "KRKMNZ007",
    "Quantity (total number)": 3,
    "Measurement type": "ML",
    "Unit Capacity (weight/volume)": 500,
    "Taxable Unit Amount": 392.661,
    "Taxable Total Amount": 1177.983,
    "Total Amount (Incl. GST)": 1236.88215
  },
  {
    "Company name (purchased from)": "SRI BHAVANI AGRI CLINIC",
    "Company GSTIN": "29AEKFS3960F1ZN",
    "Purchase date": "27.01.2026",
    "Purchase invoice number": "P-SBAC-4033",
    "Product name": "COREON",
    "Category": "HERBISIDE",
    "GST (%)": 18,
    "HSN": "38089290",
    "Batch no.": "25L6272101",
    "Quantity (total number)": 5,
    "Measurement type": "ML",
    "Unit Capacity (weight/volume)": 800,
    "Taxable Unit Amount": 845,
    "Taxable Total Amount": 4225,
    "Total Amount (Incl. GST)": 4985.5
  },
  {
    "Company name (purchased from)": "SRI BHAVANI AGRI CLINIC",
    "Company GSTIN": "29AEKFS3960F1ZN",
    "Purchase date": "22.08.2025",
    "Purchase invoice number": "P-SBAC-2270",
    "Product name": "ASSERT",
    "Category": "HERBISIDE",
    "GST (%)": 18,
    "HSN": "3808",
    "Batch no.": "C691IP44AS1",
    "Quantity (total number)": 2,
    "Measurement type": "ML",
    "Unit Capacity (weight/volume)": 400,
    "Taxable Unit Amount": 660,
    "Taxable Total Amount": 1320,
    "Total Amount (Incl. GST)": 1557.6
  },
  {
    "Company name (purchased from)": "SRI BHAVANI AGRI CLINIC",
    "Company GSTIN": "29AEKFS3960F1ZN",
    "Purchase date": "02.02.2026",
    "Purchase invoice number": "P-SBAC-4098",
    "Product name": "DANITOL",
    "Category": "INSECTICIDE",
    "GST (%)": 18,
    "HSN": "38089199",
    "Batch no.": "VDTL508157",
    "Quantity (total number)": 10,
    "Measurement type": "ML",
    "Unit Capacity (weight/volume)": 500,
    "Taxable Unit Amount": 288,
    "Taxable Total Amount": 2880,
    "Total Amount (Incl. GST)": 3398.4
  },
  {
    "Company name (purchased from)": "SRI BHAVANI AGRI CLINIC",
    "Company GSTIN": "29AEKFS3960F1ZN",
    "Purchase date": "---",
    "Purchase invoice number": "---",
    "Product name": "NAVAXOIDE",
    "Category": "HERBISIDE",
    "GST (%)": 18,
    "HSN": "3808",
    "Batch no.": "",
    "Quantity (total number)": 6,
    "Measurement type": "ML",
    "Unit Capacity (weight/volume)": 500,
    "Taxable Unit Amount": 1356.78,
    "Taxable Total Amount": 8140.68,
    "Total Amount (Incl. GST)": 9606.0024
  },
  {
    "Company name (purchased from)": "KR LIFE SCIENCE PVT LTD",
    "Company GSTIN": "29AAICK5339B1ZI",
    "Purchase date": "30.12.2026",
    "Purchase invoice number": "111/P/2526/08179",
    "Product name": "SUREKILL",
    "Category": "HERBISIDE",
    "GST (%)": 18,
    "HSN": "38089990",
    "Batch no.": "KRK1451",
    "Quantity (total number)": 85,
    "Measurement type": "GM",
    "Unit Capacity (weight/volume)": 100,
    "Taxable Unit Amount": 42.3225,
    "Taxable Total Amount": 3597.4125,
    "Total Amount (Incl. GST)": 4244.94675
  },
  {
    "Company name (purchased from)": "KR LIFE SCIENCE PVT LTD",
    "Company GSTIN": "29AAICK5339B1ZI",
    "Purchase date": "30.12.2026",
    "Purchase invoice number": "111/P/2526/08179",
    "Product name": "SUREKILL",
    "Category": "HERBISIDE",
    "GST (%)": 18,
    "HSN": "38089990",
    "Batch no.": "KRK1456",
    "Quantity (total number)": 15,
    "Measurement type": "GM",
    "Unit Capacity (weight/volume)": 500,
    "Taxable Unit Amount": 192.8025,
    "Taxable Total Amount": 2892.0375,
    "Total Amount (Incl. GST)": 3412.60425
  },
  {
    "Company name (purchased from)": "KR LIFE SCIENCE PVT LTD",
    "Company GSTIN": "29AAICK5339B1ZI",
    "Purchase date": "30.12.2026",
    "Purchase invoice number": "111/P/2526/08179",
    "Product name": "SUREKILL",
    "Category": "HERBISIDE",
    "GST (%)": 18,
    "HSN": "38089990",
    "Batch no.": "KRK1440",
    "Quantity (total number)": 30,
    "Measurement type": "KG",
    "Unit Capacity (weight/volume)": 1,
    "Taxable Unit Amount": 376.2,
    "Taxable Total Amount": 11286,
    "Total Amount (Incl. GST)": 13317.48
  },
  {
    "Company name (purchased from)": "KR LIFE SCIENCE PVT LTD",
    "Company GSTIN": "29AAICK5339B1ZI",
    "Purchase date": "10.07.2025",
    "Purchase invoice number": "111/P/2526/08197",
    "Product name": "JEMSTAR",
    "Category": "INSECTICIDE",
    "GST (%)": 18,
    "HSN": "3808",
    "Batch no.": "KRK828",
    "Quantity (total number)": 4,
    "Measurement type": "GM",
    "Unit Capacity (weight/volume)": 250,
    "Taxable Unit Amount": 254.405,
    "Taxable Total Amount": 1017.62,
    "Total Amount (Incl. GST)": 1200.7916
  },
  {
    "Company name (purchased from)": "KR LIFE SCIENCE PVT LTD",
    "Company GSTIN": "29AAICK5339B1ZI",
    "Purchase date": "10.07.2025",
    "Purchase invoice number": "111/P/2526/08197",
    "Product name": "JEMSTAR",
    "Category": "INSECTICIDE",
    "GST (%)": 18,
    "HSN": "3808",
    "Batch no.": "KRK828",
    "Quantity (total number)": 30,
    "Measurement type": "GM",
    "Unit Capacity (weight/volume)": 100,
    "Taxable Unit Amount": 225.72,
    "Taxable Total Amount": 6771.6,
    "Total Amount (Incl. GST)": 7990.488
  },
  {
    "Company name (purchased from)": "KR LIFE SCIENCE PVT LTD",
    "Company GSTIN": "29AAICK5339B1ZI",
    "Purchase date": "27-01-2026",
    "Purchase invoice number": "111/P/2526/08733",
    "Product name": "KRIM",
    "Category": "HERBISIDE",
    "GST (%)": 18,
    "HSN": "38089390",
    "Batch no.": "KRK2M004",
    "Quantity (total number)": 7,
    "Measurement type": "ML",
    "Unit Capacity (weight/volume)": 400,
    "Taxable Unit Amount": 409.1185,
    "Taxable Total Amount": 2863.8295,
    "Total Amount (Incl. GST)": 3379.31881
  },
  {
    "Company name (purchased from)": "KR LIFE SCIENCE PVT LTD",
    "Company GSTIN": "29AAICK5339B1ZI",
    "Purchase date": "27-01-2026",
    "Purchase invoice number": "111/P/2526/08733",
    "Product name": "PRINCE",
    "Category": "INSECTICIDE",
    "GST (%)": 18,
    "HSN": "38089990",
    "Batch no.": "KRRPR0879",
    "Quantity (total number)": 31,
    "Measurement type": "LTR",
    "Unit Capacity (weight/volume)": 1,
    "Taxable Unit Amount": 338.58,
    "Taxable Total Amount": 10495.98,
    "Total Amount (Incl. GST)": 12385.2564
  },
  {
    "Company name (purchased from)": "KR LIFE SCIENCE PVT LTD",
    "Company GSTIN": "29AAICK5339B1ZI",
    "Purchase date": "27-01-2026",
    "Purchase invoice number": "111/P/2526/08389",
    "Product name": "PRINCE",
    "Category": "INSECTICIDE",
    "GST (%)": 18,
    "HSN": "38089990",
    "Batch no.": "KRRPR0888",
    "Quantity (total number)": 12,
    "Measurement type": "ML",
    "Unit Capacity (weight/volume)": 500,
    "Taxable Unit Amount": 174,
    "Taxable Total Amount": 2088,
    "Total Amount (Incl. GST)": 2463.84
  },
  {
    "Company name (purchased from)": "KR LIFE SCIENCE PVT LTD",
    "Company GSTIN": "29AAICK5339B1ZI",
    "Purchase date": "27-01-2026",
    "Purchase invoice number": "111/P/2526/08389",
    "Product name": "KREEPER",
    "Category": "INSECTICIDE",
    "GST (%)": 18,
    "HSN": "38089990",
    "Batch no.": "KRK228",
    "Quantity (total number)": 17,
    "Measurement type": "GM",
    "Unit Capacity (weight/volume)": 80,
    "Taxable Unit Amount": 108.1577,
    "Taxable Total Amount": 1838.6809,
    "Total Amount (Incl. GST)": 2169.643462
  },
  {
    "Company name (purchased from)": "NICHINO PRIVATE LTD",
    "Company GSTIN": "29AAECV6642E1Z5",
    "Purchase date": "28.8.2025",
    "Purchase invoice number": "2534201213",
    "Product name": "O-DUET",
    "Category": "INSECTICIDE",
    "GST (%)": 18,
    "HSN": "38089990",
    "Batch no.": "J250DA2027",
    "Quantity (total number)": 26,
    "Measurement type": "GM",
    "Unit Capacity (weight/volume)": 280,
    "Taxable Unit Amount": 851,
    "Taxable Total Amount": 22126,
    "Total Amount (Incl. GST)": 26108.68
  },
  {
    "Company name (purchased from)": "NICHINO PRIVATE LTD",
    "Company GSTIN": "29AAECV6642E1Z5",
    "Purchase date": "28.8.2026",
    "Purchase invoice number": "2534201213",
    "Product name": "O-DUET",
    "Category": "INSECTICIDE",
    "GST (%)": 18,
    "HSN": "38089990",
    "Batch no.": "J250DA2018",
    "Quantity (total number)": 5,
    "Measurement type": "GM",
    "Unit Capacity (weight/volume)": 700,
    "Taxable Unit Amount": 2059.65,
    "Taxable Total Amount": 10298.25,
    "Total Amount (Incl. GST)": 12151.935
  },
  {
    "Company name (purchased from)": "NICHINO PRIVATE LTD",
    "Company GSTIN": "29AAECV6642E1Z5",
    "Purchase date": "28-7-2025",
    "Purchase invoice number": "2534102105",
    "Product name": "KARSHAK",
    "Category": "ORGANIC GRANULS",
    "GST (%)": 5,
    "HSN": "31010099",
    "Batch no.": "AN/GR/01-001",
    "Quantity (total number)": 30,
    "Measurement type": "KG",
    "Unit Capacity (weight/volume)": 4,
    "Taxable Unit Amount": 566.05,
    "Taxable Total Amount": 16981.5,
    "Total Amount (Incl. GST)": 17830.575
  },
  {
    "Company name (purchased from)": "NICHINO PRIVATE LTD",
    "Company GSTIN": "29AAECV6642E1Z6",
    "Purchase date": "09.02.2026",
    "Purchase invoice number": "2534104771",
    "Product name": "SHORI",
    "Category": "INSECTICIDE",
    "GST (%)": 18,
    "HSN": "38089910",
    "Batch no.": "P25SHA3095",
    "Quantity (total number)": 15,
    "Measurement type": "KG",
    "Unit Capacity (weight/volume)": 5,
    "Taxable Unit Amount": 699.95,
    "Taxable Total Amount": 10499.25,
    "Total Amount (Incl. GST)": 12389.115
  },
  {
    "Company name (purchased from)": "NICHINO PRIVATE LTD",
    "Company GSTIN": "29AAECV6642E1Z7",
    "Purchase date": "13-1-2026",
    "Purchase invoice number": "2534202437",
    "Product name": "PRIME",
    "Category": "INSECTICIDE",
    "GST (%)": 18,
    "HSN": "38089990",
    "Batch no.": "J25PRA2059",
    "Quantity (total number)": 42,
    "Measurement type": "GM",
    "Unit Capacity (weight/volume)": 100,
    "Taxable Unit Amount": 80,
    "Taxable Total Amount": 3360,
    "Total Amount (Incl. GST)": 3964.8
  },
  {
    "Company name (purchased from)": "NICHINO PRIVATE LTD",
    "Company GSTIN": "29AAECV6642E1Z7",
    "Purchase date": "13-1-2026",
    "Purchase invoice number": "2534202437",
    "Product name": "PRIME",
    "Category": "INSECTICIDE",
    "GST (%)": 18,
    "HSN": "38089990",
    "Batch no.": "J25PRA2059",
    "Quantity (total number)": 4,
    "Measurement type": "GM",
    "Unit Capacity (weight/volume)": 50,
    "Taxable Unit Amount": 40,
    "Taxable Total Amount": 160,
    "Total Amount (Incl. GST)": 188.8
  },
  {
    "Company name (purchased from)": "NICHINO PRIVATE LTD",
    "Company GSTIN": "29AAECV6642E1Z8",
    "Purchase date": "23-2-2026",
    "Purchase invoice number": "2534104886",
    "Product name": "DAIWIK",
    "Category": "ORGANIC LIQUID",
    "GST (%)": 5,
    "HSN": "31010099",
    "Batch no.": "DA2407005",
    "Quantity (total number)": 20,
    "Measurement type": "ML",
    "Unit Capacity (weight/volume)": 500,
    "Taxable Unit Amount": 425.4,
    "Taxable Total Amount": 8508,
    "Total Amount (Incl. GST)": 8933.4
  },
  {
    "Company name (purchased from)": "NICHINO PRIVATE LTD",
    "Company GSTIN": "29AAECV6642E1Z9",
    "Purchase date": "23-2-2026",
    "Purchase invoice number": "2534104886",
    "Product name": "DAIWIK",
    "Category": "ORGANIC LIQUID",
    "GST (%)": 5,
    "HSN": "31010099",
    "Batch no.": "DA2407004",
    "Quantity (total number)": 1,
    "Measurement type": "LTR",
    "Unit Capacity (weight/volume)": 1,
    "Taxable Unit Amount": 808.25,
    "Taxable Total Amount": 808.25,
    "Total Amount (Incl. GST)": 848.6625
  },
  {
    "Company name (purchased from)": "NICHINO PRIVATE LTD",
    "Company GSTIN": "29AAECV6642E1Z9",
    "Purchase date": "23-2-2026",
    "Purchase invoice number": "2434202722",
    "Product name": "TOPTOO",
    "Category": "FUNGUCIDE",
    "GST (%)": 18,
    "HSN": "380892199",
    "Batch no.": "J25TOA2039",
    "Quantity (total number)": 4,
    "Measurement type": "KG",
    "Unit Capacity (weight/volume)": 1,
    "Taxable Unit Amount": 463.85,
    "Taxable Total Amount": 1855.4,
    "Total Amount (Incl. GST)": 2189.372
  },
  {
    "Company name (purchased from)": "NICHINO PRIVATE LTD",
    "Company GSTIN": "29AAECV6642E1Z9",
    "Purchase date": "23-2-2026",
    "Purchase invoice number": "2434202722",
    "Product name": "TOPTOO",
    "Category": "FUNGUCIDE",
    "GST (%)": 18,
    "HSN": "380892199",
    "Batch no.": "J25TOA2042",
    "Quantity (total number)": 24,
    "Measurement type": "GM",
    "Unit Capacity (weight/volume)": 500,
    "Taxable Unit Amount": 244.7,
    "Taxable Total Amount": 5872.8,
    "Total Amount (Incl. GST)": 6929.904
  },
  {
    "Company name (purchased from)": "NICHINO PRIVATE LTD",
    "Company GSTIN": "29AAECV6642E1Z9",
    "Purchase date": "23-2-2026",
    "Purchase invoice number": "2434202722",
    "Product name": "TOPTOO",
    "Category": "FUNGUCIDE",
    "GST (%)": 18,
    "HSN": "380892199",
    "Batch no.": "J25TOA2043",
    "Quantity (total number)": 48,
    "Measurement type": "GM",
    "Unit Capacity (weight/volume)": 250,
    "Taxable Unit Amount": 125,
    "Taxable Total Amount": 6000,
    "Total Amount (Incl. GST)": 7080
  },
  {
    "Company name (purchased from)": "NICHINO PRIVATE LTD",
    "Company GSTIN": "29AAECV6642E1Z9",
    "Purchase date": "23-2-2027",
    "Purchase invoice number": "2434202722",
    "Product name": "WARTAP 50 SP",
    "Category": "INSECTICIDE",
    "GST (%)": 18,
    "HSN": "380892199",
    "Batch no.": "J25TOA2039",
    "Quantity (total number)": 15,
    "Measurement type": "GM",
    "Unit Capacity (weight/volume)": 500,
    "Taxable Unit Amount": 551.25,
    "Taxable Total Amount": 8268.75,
    "Total Amount (Incl. GST)": 9757.125
  },
  {
    "Company name (purchased from)": "NICHINO PRIVATE LTD",
    "Company GSTIN": "29AAECV6642E1Z9",
    "Purchase date": "09.02.2026",
    "Purchase invoice number": "2534104771",
    "Product name": "SHAN",
    "Category": "FUNGUCIDE",
    "GST (%)": 18,
    "HSN": "38089290",
    "Batch no.": "B25SHA1019",
    "Quantity (total number)": 8,
    "Measurement type": "ML",
    "Unit Capacity (weight/volume)": 500,
    "Taxable Unit Amount": 625.4,
    "Taxable Total Amount": 5003.2,
    "Total Amount (Incl. GST)": 5903.776
  },
  {
    "Company name (purchased from)": "NICHINO PRIVATE LTD",
    "Company GSTIN": "29AAECV6642E1Z9",
    "Purchase date": "13.02.2026",
    "Purchase invoice number": "2534202678",
    "Product name": "CONZOLE PREMIUM",
    "Category": "FUNGUCIDE",
    "GST (%)": 18,
    "HSN": "38089199",
    "Batch no.": "J25CPA2057",
    "Quantity (total number)": 4,
    "Measurement type": "LTR",
    "Unit Capacity (weight/volume)": 1,
    "Taxable Unit Amount": 226.35,
    "Taxable Total Amount": 905.4,
    "Total Amount (Incl. GST)": 1068.372
  },
  {
    "Company name (purchased from)": "NICHINO PRIVATE LTD",
    "Company GSTIN": "29AAECV6642E1Z9",
    "Purchase date": "23.02.2026",
    "Purchase invoice number": "2534104883",
    "Product name": "ACHUBU",
    "Category": "FUNGUCIDE",
    "GST (%)": 18,
    "HSN": "38089290",
    "Batch no.": "B24ABB1010",
    "Quantity (total number)": 26,
    "Measurement type": "ML",
    "Unit Capacity (weight/volume)": 400,
    "Taxable Unit Amount": 716.85,
    "Taxable Total Amount": 18638.1,
    "Total Amount (Incl. GST)": 21992.958
  },
  {
    "Company name (purchased from)": "NICHINO PRIVATE LTD",
    "Company GSTIN": "29AAECV6642E1Z9",
    "Purchase date": "23.02.2026",
    "Purchase invoice number": "2534104883",
    "Product name": "LAND RIDER",
    "Category": "HERBICIDE",
    "GST (%)": 18,
    "HSN": "38089990",
    "Batch no.": "B24LRA1001",
    "Quantity (total number)": 13,
    "Measurement type": "ML",
    "Unit Capacity (weight/volume)": 200,
    "Taxable Unit Amount": 338,
    "Taxable Total Amount": 4394,
    "Total Amount (Incl. GST)": 5184.92
  },
  {
    "Company name (purchased from)": "NICHINO PRIVATE LTD",
    "Company GSTIN": "29AAECV6642E1Z9",
    "Purchase date": "23.02.2026",
    "Purchase invoice number": "2534104883",
    "Product name": "ARASHI",
    "Category": "INSECTICIDE",
    "GST (%)": 18,
    "HSN": "38089199",
    "Batch no.": "B25AHA1005",
    "Quantity (total number)": 66,
    "Measurement type": "ML",
    "Unit Capacity (weight/volume)": 150,
    "Taxable Unit Amount": 408.75,
    "Taxable Total Amount": 26977.5,
    "Total Amount (Incl. GST)": 31833.45
  },
  {
    "Company name (purchased from)": "NICHINO PRIVATE LTD",
    "Company GSTIN": "29AAECV6642E1Z9",
    "Purchase date": "05.12.2025",
    "Purchase invoice number": "2534103926",
    "Product name": "ARASHI",
    "Category": "INSECTICIDE",
    "GST (%)": 18,
    "HSN": "38089199",
    "Batch no.": "B25AHA1006",
    "Quantity (total number)": 73,
    "Measurement type": "ML",
    "Unit Capacity (weight/volume)": 60,
    "Taxable Unit Amount": 174.85,
    "Taxable Total Amount": 12764.05,
    "Total Amount (Incl. GST)": 15061.579
  },
  {
    "Company name (purchased from)": "NICHINO PRIVATE LTD",
    "Company GSTIN": "29AAECV6642E1Z9",
    "Purchase date": "23.02.2026",
    "Purchase invoice number": "2531202281",
    "Product name": "COMA",
    "Category": "INSECTICIDE",
    "GST (%)": 18,
    "HSN": "380889199",
    "Batch no.": "J25CMA2015",
    "Quantity (total number)": 8,
    "Measurement type": "LTR",
    "Unit Capacity (weight/volume)": 1,
    "Taxable Unit Amount": 519.15,
    "Taxable Total Amount": 4153.2,
    "Total Amount (Incl. GST)": 4900.776
  },
  {
    "Company name (purchased from)": "NICHINO PRIVATE LTD",
    "Company GSTIN": "29AAECV6642E1Z9",
    "Purchase date": "24.02.26",
    "Purchase invoice number": "2534202734",
    "Product name": "CHANDIKA",
    "Category": "INSECTICIDE",
    "GST (%)": 18,
    "HSN": "38089990",
    "Batch no.": "J25CHA2024",
    "Quantity (total number)": 22,
    "Measurement type": "LTR",
    "Unit Capacity (weight/volume)": 1,
    "Taxable Unit Amount": 565.35,
    "Taxable Total Amount": 12437.7,
    "Total Amount (Incl. GST)": 14676.486
  },
  {
    "Company name (purchased from)": "NICHINO PRIVATE LTD",
    "Company GSTIN": "29AAECV6642E1Z9",
    "Purchase date": "20.12.2025",
    "Purchase invoice number": "2534104135",
    "Product name": "BUSIDO",
    "Category": "INSECTICIDE",
    "GST (%)": 18,
    "HSN": "38089199",
    "Batch no.": "B25BUA1001",
    "Quantity (total number)": 25,
    "Measurement type": "ML",
    "Unit Capacity (weight/volume)": 250,
    "Taxable Unit Amount": 380.75,
    "Taxable Total Amount": 9518.75,
    "Total Amount (Incl. GST)": 11232.125
  },
  {
    "Company name (purchased from)": "NICHINO PRIVATE LTD",
    "Company GSTIN": "29AAECV6642E1Z9",
    "Purchase date": "13.01.2026",
    "Purchase invoice number": "2534202437",
    "Product name": "CHANDIKA",
    "Category": "INSECTICIDE",
    "GST (%)": 18,
    "HSN": "38089990",
    "Batch no.": "J25CHA2014",
    "Quantity (total number)": 28,
    "Measurement type": "ML",
    "Unit Capacity (weight/volume)": 250,
    "Taxable Unit Amount": 152,
    "Taxable Total Amount": 4256,
    "Total Amount (Incl. GST)": 5022.08
  },
  {
    "Company name (purchased from)": "NICHINO PRIVATE LTD",
    "Company GSTIN": "29AAECV6642E1Z9",
    "Purchase date": "13.02.2026",
    "Purchase invoice number": "2534104816",
    "Product name": "HIROTA",
    "Category": "INSECTICIDE",
    "GST (%)": 18,
    "HSN": "38089199",
    "Batch no.": "B25THA1003",
    "Quantity (total number)": 20,
    "Measurement type": "ML",
    "Unit Capacity (weight/volume)": 250,
    "Taxable Unit Amount": 200.35,
    "Taxable Total Amount": 4007,
    "Total Amount (Incl. GST)": 4728.26
  },
  {
    "Company name (purchased from)": "MAHADHAN AGRITECH LIMITED",
    "Company GSTIN": "29AACCA5046P1Z9",
    "Purchase date": "29.10.2025",
    "Purchase invoice number": "F20000513125",
    "Product name": "ZINK+",
    "Category": "ZINCATED BENSULF",
    "GST (%)": 5,
    "HSN": "25030090",
    "Batch no.": "PN2204168",
    "Quantity (total number)": 7,
    "Measurement type": "KG",
    "Unit Capacity (weight/volume)": 5,
    "Taxable Unit Amount": 466.67,
    "Taxable Total Amount": 3266.69,
    "Total Amount (Incl. GST)": 3299.3569
  },
  {
    "Company name (purchased from)": "MAHADHAN AGRITECH LIMITED",
    "Company GSTIN": "29AACCA5046P1Z10",
    "Purchase date": "29.10.2026",
    "Purchase invoice number": "F20000513122",
    "Product name": "SUPERPAST BENSULF",
    "Category": "SULFUR",
    "GST (%)": 5,
    "HSN": "30011150090",
    "Batch no.": "250803C",
    "Quantity (total number)": 16,
    "Measurement type": "KG",
    "Unit Capacity (weight/volume)": 10,
    "Taxable Unit Amount": 566.67,
    "Taxable Total Amount": 9066.72,
    "Total Amount (Incl. GST)": 9520.056
  },
  {
    "Company name (purchased from)": "MAHADHAN AGRITECH LIMITED",
    "Company GSTIN": "29AACCA5046P1Z11",
    "Purchase date": "21.07.2025",
    "Purchase invoice number": "F20000507137",
    "Product name": "12.61.00",
    "Category": "WATER SOLVABLE",
    "GST (%)": 5,
    "HSN": "31054000",
    "Batch no.": "24080806",
    "Quantity (total number)": 51,
    "Measurement type": "KG",
    "Unit Capacity (weight/volume)": 1,
    "Taxable Unit Amount": 171.43,
    "Taxable Total Amount": 8742.93,
    "Total Amount (Incl. GST)": 9180.0765
  },
  {
    "Company name (purchased from)": "MAHADHAN AGRITECH LIMITED",
    "Company GSTIN": "29AACCA5046P1Z11",
    "Purchase date": "21.07.2025",
    "Purchase invoice number": "F20000507137",
    "Product name": "19.19.19",
    "Category": "WATER SOLVABLE",
    "GST (%)": 5,
    "HSN": "31052000",
    "Batch no.": "SN250614",
    "Quantity (total number)": 30,
    "Measurement type": "KG",
    "Unit Capacity (weight/volume)": 1,
    "Taxable Unit Amount": 137.14,
    "Taxable Total Amount": 4114.2,
    "Total Amount (Incl. GST)": 4319.91
  },
  {
    "Company name (purchased from)": "SHANMUKHA AGRITECH LIMITED",
    "Company GSTIN": "29AAPCS8870E1ZN",
    "Purchase date": "03.09.2025",
    "Purchase invoice number": "DAVSB2526-4941",
    "Product name": "TEFEX SUPER",
    "Category": "INSECTICIDE",
    "GST (%)": 18,
    "HSN": "38089910",
    "Batch no.": "HL25TXS050",
    "Quantity (total number)": 6,
    "Measurement type": "ML",
    "Unit Capacity (weight/volume)": 500,
    "Taxable Unit Amount": 260,
    "Taxable Total Amount": 1560,
    "Total Amount (Incl. GST)": 1840.8
  },
  {
    "Company name (purchased from)": "SHANMUKHA AGRITECH LIMITED",
    "Company GSTIN": "29AAPCS8870E1ZN",
    "Purchase date": "03.09.2025",
    "Purchase invoice number": "DAVSB2526-4941",
    "Product name": "TEFEX SUPER",
    "Category": "INSECTICIDE",
    "GST (%)": 18,
    "HSN": "38089910",
    "Batch no.": "HL25TXS049",
    "Quantity (total number)": 16,
    "Measurement type": "ML",
    "Unit Capacity (weight/volume)": 250,
    "Taxable Unit Amount": 138,
    "Taxable Total Amount": 2208,
    "Total Amount (Incl. GST)": 2605.44
  },
  {
    "Company name (purchased from)": "SHANMUKHA AGRITECH LIMITED",
    "Company GSTIN": "29AAPCS8870E1ZN",
    "Purchase date": "11.12.2025",
    "Purchase invoice number": "326DV01597",
    "Product name": "LUMIA PLUS",
    "Category": "INSECTICIDE",
    "GST (%)": 18,
    "HSN": "38089910",
    "Batch no.": "HL24LUP001",
    "Quantity (total number)": 21,
    "Measurement type": "ML",
    "Unit Capacity (weight/volume)": 200,
    "Taxable Unit Amount": 837,
    "Taxable Total Amount": 17577,
    "Total Amount (Incl. GST)": 20740.86
  },
  {
    "Company name (purchased from)": "SHANMUKHA AGRITECH LIMITED",
    "Company GSTIN": "29AAPCS8870E1ZN",
    "Purchase date": "26.02.2026",
    "Purchase invoice number": "326DVO3386",
    "Product name": "WEED BLAZE",
    "Category": "HERBICIDE",
    "GST (%)": 18,
    "HSN": "38089910",
    "Batch no.": "HL25WB006",
    "Quantity (total number)": 20,
    "Measurement type": "LTR",
    "Unit Capacity (weight/volume)": 1,
    "Taxable Unit Amount": 275,
    "Taxable Total Amount": 5500,
    "Total Amount (Incl. GST)": 6490
  },
  {
    "Company name (purchased from)": "KAVERI MICROTECK PVT LIMITED",
    "Company GSTIN": "29AAFCK2429K1Z9",
    "Purchase date": "13.06.2025",
    "Purchase invoice number": "MSRIDV25-26/0187",
    "Product name": "MAZIK PLUS",
    "Category": "MICRO NUTRIENT",
    "GST (%)": 5,
    "HSN": "28332610",
    "Batch no.": "8",
    "Quantity (total number)": 19,
    "Measurement type": "GM",
    "Unit Capacity (weight/volume)": 400,
    "Taxable Unit Amount": 220,
    "Taxable Total Amount": 4180,
    "Total Amount (Incl. GST)": 4389
  },
  {
    "Company name (purchased from)": "KAVERI MICROTECK PVT LIMITED",
    "Company GSTIN": "29AAFCK2429K1Z9",
    "Purchase date": "13.06.2025",
    "Purchase invoice number": "MSRIDV25-26/0187",
    "Product name": "SPREAD",
    "Category": "SPREADER",
    "GST (%)": 5,
    "HSN": "31010099",
    "Batch no.": "25KKF99SP005",
    "Quantity (total number)": 3,
    "Measurement type": "ML",
    "Unit Capacity (weight/volume)": 100,
    "Taxable Unit Amount": 83,
    "Taxable Total Amount": 249,
    "Total Amount (Incl. GST)": 261.45
  },
  {
    "Company name (purchased from)": "KAVERI MICROTECK PVT LIMITED",
    "Company GSTIN": "29AAFCK2429K1Z9",
    "Purchase date": "13.06.2025",
    "Purchase invoice number": "MSRIDV25-26/0187",
    "Product name": "SPREAD",
    "Category": "SPREADER",
    "GST (%)": 5,
    "HSN": "31010099",
    "Batch no.": "60",
    "Quantity (total number)": 2,
    "Measurement type": "ML",
    "Unit Capacity (weight/volume)": 250,
    "Taxable Unit Amount": 165,
    "Taxable Total Amount": 330,
    "Total Amount (Incl. GST)": 346.5
  },
  {
    "Company name (purchased from)": "SHANMUKHA AGRITECH LIMITED",
    "Company GSTIN": "29AAPCS8870E1ZN",
    "Purchase date": "24/02/2026",
    "Purchase invoice number": "326DV03344",
    "Product name": "NUTRI STAR",
    "Category": "NUTRIENTS",
    "GST (%)": 5,
    "HSN": "31010099",
    "Batch no.": "GM26NS001",
    "Quantity (total number)": 2,
    "Measurement type": "KG",
    "Unit Capacity (weight/volume)": 13,
    "Taxable Unit Amount": 1879.176,
    "Taxable Total Amount": 3758.352,
    "Total Amount (Incl. GST)": 3946.2696
  },
  {
    "Company name (purchased from)": "SHANMUKHA AGRITECH LIMITED",
    "Company GSTIN": "29AAPCS8870E1ZN",
    "Purchase date": "23/03/2026",
    "Purchase invoice number": "326DV03899",
    "Product name": "NUTRI STAR",
    "Category": "NUTRIENTS",
    "GST (%)": 5,
    "HSN": "31010099",
    "Batch no.": "GM26NS001",
    "Quantity (total number)": 2,
    "Measurement type": "KG",
    "Unit Capacity (weight/volume)": 13,
    "Taxable Unit Amount": 1879.176,
    "Taxable Total Amount": 3758.352,
    "Total Amount (Incl. GST)": 3946.2696
  },
  {
    "Company name (purchased from)": "SHANMUKHA AGRITECH LIMITED",
    "Company GSTIN": "29AAPCS8870E1ZN",
    "Purchase date": "23/03/2026",
    "Purchase invoice number": "326DV03899",
    "Product name": "PASIDI 6",
    "Category": "INSECTICIDE",
    "GST (%)": 5,
    "HSN": "31010099",
    "Batch no.": "GM26NS001",
    "Quantity (total number)": 50,
    "Measurement type": "ML",
    "Unit Capacity (weight/volume)": 100,
    "Taxable Unit Amount": 575.2,
    "Taxable Total Amount": 28760,
    "Total Amount (Incl. GST)": 30198
  },
  {
    "Company name (purchased from)": "SHANMUKHA AGRITECH LIMITED",
    "Company GSTIN": "29AAPCS8870E1ZN",
    "Purchase date": "28/03/2026",
    "Purchase invoice number": "326DV03899",
    "Product name": "NUTRI STAR",
    "Category": "NUTRIENTS",
    "GST (%)": 5,
    "HSN": "31010099",
    "Batch no.": "GM26NS004",
    "Quantity (total number)": 3,
    "Measurement type": "KG",
    "Unit Capacity (weight/volume)": 13,
    "Taxable Unit Amount": 1879.176,
    "Taxable Total Amount": 5637.528,
    "Total Amount (Incl. GST)": 5919.4044
  },
  {
    "Company name (purchased from)": "SHANMUKHA AGRITECH LIMITED",
    "Company GSTIN": "29AAPCS8870E1ZN",
    "Purchase date": "28/03/2026",
    "Purchase invoice number": "326DV03899",
    "Product name": "JAMINDAR",
    "Category": "GROWTH PROMOTER",
    "GST (%)": 5,
    "HSN": "31010099",
    "Batch no.": "MN26JD001",
    "Quantity (total number)": 10,
    "Measurement type": "LTR",
    "Unit Capacity (weight/volume)": 1,
    "Taxable Unit Amount": 400.8,
    "Taxable Total Amount": 4008,
    "Total Amount (Incl. GST)": 4208.4
  },
  {
    "Company name (purchased from)": "SHANMUKHA AGRITECH LIMITED",
    "Company GSTIN": "29AAPCS8870E1ZN",
    "Purchase date": "28/03/2026",
    "Purchase invoice number": "326DV03899",
    "Product name": "JAMINDAR",
    "Category": "GROWTH PROMOTER",
    "GST (%)": 5,
    "HSN": "31010099",
    "Batch no.": "MN26JD002",
    "Quantity (total number)": 20,
    "Measurement type": "ML",
    "Unit Capacity (weight/volume)": 500,
    "Taxable Unit Amount": 223.2,
    "Taxable Total Amount": 4464,
    "Total Amount (Incl. GST)": 4687.2
  },
  {
    "Company name (purchased from)": "KR LIFE SCIENCE PVT LTD",
    "Company GSTIN": "29AAICK5339B1ZI",
    "Purchase date": "29/07/2025",
    "Purchase invoice number": "111/P/25-26/03213",
    "Product name": "KRUP",
    "Category": "HERBICIDE",
    "GST (%)": 18,
    "HSN": "38089350",
    "Batch no.": "KRR0463",
    "Quantity (total number)": 3,
    "Measurement type": "ML",
    "Unit Capacity (weight/volume)": 500,
    "Taxable Unit Amount": 138.726,
    "Taxable Total Amount": 416.178,
    "Total Amount (Incl. GST)": 491.09004
  },
  {
    "Company name (purchased from)": "AAMRUT ORGANIC FERTILIZERS",
    "Company GSTIN": "29AAWFA0365Q1ZL",
    "Purchase date": "14/03/2026",
    "Purchase invoice number": "25/26-D5854",
    "Product name": "GOKUL",
    "Category": "ORGANIC MANURE",
    "GST (%)": 5,
    "HSN": "31010010",
    "Batch no.": "AG/004",
    "Quantity (total number)": 60,
    "Measurement type": "KG",
    "Unit Capacity (weight/volume)": 50,
    "Taxable Unit Amount": 900,
    "Taxable Total Amount": 54000,
    "Total Amount (Incl. GST)": 56700
  },
  {
    "Company name (purchased from)": "AAMRUT ORGANIC FERTILIZERS",
    "Company GSTIN": "29AAWFA0365Q1ZL",
    "Purchase date": "14/03/2026",
    "Purchase invoice number": "25/26-D5854",
    "Product name": "AKLTRASET",
    "Category": "SOIL CONDTIONER",
    "GST (%)": 5,
    "HSN": "31010010",
    "Batch no.": "200176A/GR",
    "Quantity (total number)": 40,
    "Measurement type": "KG",
    "Unit Capacity (weight/volume)": 50,
    "Taxable Unit Amount": 490,
    "Taxable Total Amount": 19600,
    "Total Amount (Incl. GST)": 20580
  },
  {
    "Company name (purchased from)": "KR LIFE SCIENCE PVT LTD",
    "Company GSTIN": "29AAICK5339B1ZI",
    "Purchase date": "31-01-26",
    "Purchase invoice number": "111/P/2526/08925",
    "Product name": "KIRSHIZA",
    "Category": "ORGANIC GRANULS",
    "GST (%)": 5,
    "HSN": "310100",
    "Batch no.": "KRKORG552",
    "Quantity (total number)": 185,
    "Measurement type": "KG",
    "Unit Capacity (weight/volume)": 4,
    "Taxable Unit Amount": 447.696,
    "Taxable Total Amount": 82823.76,
    "Total Amount (Incl. GST)": 86964.948
  },
  {
    "Company name (purchased from)": "SURYA AGRI BIOTECH",
    "Company GSTIN": "36AFFFS7187C1ZQ",
    "Purchase date": "23-12-2025",
    "Purchase invoice number": "856",
    "Product name": "VICTOR F7",
    "Category": "NUTRIENTS",
    "GST (%)": 5,
    "HSN": "28332990",
    "Batch no.": "S-12-25",
    "Quantity (total number)": 44,
    "Measurement type": "KG",
    "Unit Capacity (weight/volume)": 5,
    "Taxable Unit Amount": 585.2,
    "Taxable Total Amount": 25748.8,
    "Total Amount (Incl. GST)": 26006.288
  },
  {
    "Company name (purchased from)": "SURYA AGRI BIOTECH",
    "Company GSTIN": "36AFFFS7187C1ZQ",
    "Purchase date": "25-02-26",
    "Purchase invoice number": "1125",
    "Product name": "TAAKAT GR",
    "Category": "ORGANIC GRANULS",
    "GST (%)": 5,
    "HSN": "31010099",
    "Batch no.": "M-0525",
    "Quantity (total number)": 36,
    "Measurement type": "KG",
    "Unit Capacity (weight/volume)": 4,
    "Taxable Unit Amount": 755.37,
    "Taxable Total Amount": 27193.32,
    "Total Amount (Incl. GST)": 27465.2532
  },
  {
    "Company name (purchased from)": "SURYA AGRI BIOTECH",
    "Company GSTIN": "36AFFFS7187C1ZQ",
    "Purchase date": "28-06-2025",
    "Purchase invoice number": "57",
    "Product name": "V6",
    "Category": "NUTRIENTS",
    "GST (%)": 12,
    "HSN": "28332990",
    "Batch no.": "S-06-25",
    "Quantity (total number)": 4,
    "Measurement type": "LTR",
    "Unit Capacity (weight/volume)": 1,
    "Taxable Unit Amount": 3665.2,
    "Taxable Total Amount": 14660.8,
    "Total Amount (Incl. GST)": 14807.408
  },
  {
    "Company name (purchased from)": "SURYA AGRI BIOTECH",
    "Company GSTIN": "36AFFFS7187C1ZQ",
    "Purchase date": "28-06-2025",
    "Purchase invoice number": "57",
    "Product name": "V6",
    "Category": "NUTRIENTS",
    "GST (%)": 12,
    "HSN": "28332990",
    "Batch no.": "S-06-25",
    "Quantity (total number)": 2,
    "Measurement type": "ML",
    "Unit Capacity (weight/volume)": 500,
    "Taxable Unit Amount": 204.05,
    "Taxable Total Amount": 408.1,
    "Total Amount (Incl. GST)": 412.181
  },
  {
    "Company name (purchased from)": "GOLD FARMS PLANT TECH PVT LTD",
    "Company GSTIN": "29AACCG6125D21ZU",
    "Purchase date": "05/07/2025",
    "Purchase invoice number": "GFP/0648/25-26",
    "Product name": "REPRO",
    "Category": "SPEADER",
    "GST (%)": 18,
    "HSN": "34029099",
    "Batch no.": "----",
    "Quantity (total number)": 12,
    "Measurement type": "ML",
    "Unit Capacity (weight/volume)": 250,
    "Taxable Unit Amount": 160,
    "Taxable Total Amount": 1920,
    "Total Amount (Incl. GST)": 2265.6
  },
  {
    "Company name (purchased from)": "GOLD FARMS PLANT TECH PVT LTD",
    "Company GSTIN": "29AACCG6125D21ZU",
    "Purchase date": "05/07/2025",
    "Purchase invoice number": "GFP/0648/25-26",
    "Product name": "REPRO",
    "Category": "SPEADER",
    "GST (%)": 18,
    "HSN": "34029099",
    "Batch no.": "----",
    "Quantity (total number)": 20,
    "Measurement type": "ML",
    "Unit Capacity (weight/volume)": 500,
    "Taxable Unit Amount": 300,
    "Taxable Total Amount": 6000,
    "Total Amount (Incl. GST)": 7080
  },
  {
    "Company name (purchased from)": "GOLD FARMS PLANT TECH PVT LTD",
    "Company GSTIN": "29AACCG6125D21ZU",
    "Purchase date": "05/07/2025",
    "Purchase invoice number": "GFP/0647/25-26",
    "Product name": "MAIZE SPECIAL",
    "Category": "MICRINUTRIENTS",
    "GST (%)": 12,
    "HSN": "28332610",
    "Batch no.": "----",
    "Quantity (total number)": 15,
    "Measurement type": "KG",
    "Unit Capacity (weight/volume)": 10,
    "Taxable Unit Amount": 415.2,
    "Taxable Total Amount": 6228,
    "Total Amount (Incl. GST)": 6975.36
  },
  {
    "Company name (purchased from)": "GOLD FARMS PLANT TECH PVT LTD",
    "Company GSTIN": "29AACCG6125D21ZU",
    "Purchase date": "05/07/2025",
    "Purchase invoice number": "GFP/0646/25-26",
    "Product name": "BIOGOLD",
    "Category": "ORGANIC FERTILIZER",
    "GST (%)": 5,
    "HSN": "31010099",
    "Batch no.": "----",
    "Quantity (total number)": 5,
    "Measurement type": "KG",
    "Unit Capacity (weight/volume)": 10,
    "Taxable Unit Amount": 564,
    "Taxable Total Amount": 2820,
    "Total Amount (Incl. GST)": 2961
  },
  {
    "Company name (purchased from)": "SURYA AGRI BIOTECH",
    "Company GSTIN": "36AFFFS7187C1ZQ",
    "Purchase date": "28/06/2025",
    "Purchase invoice number": "56",
    "Product name": "GROMAX",
    "Category": "ORGANIC FERTILIZER",
    "GST (%)": 5,
    "HSN": "31010099",
    "Batch no.": "M-06-25",
    "Quantity (total number)": 2,
    "Measurement type": "KG",
    "Unit Capacity (weight/volume)": 50,
    "Taxable Unit Amount": 2858.24,
    "Taxable Total Amount": 5716.48,
    "Total Amount (Incl. GST)": 5773.6448
  },
  {
    "Company name (purchased from)": "IFFDC",
    "Company GSTIN": "29AAAAI0323F1Z6",
    "Purchase date": "11.06.2025",
    "Purchase invoice number": "2526IFDKAV003018",
    "Product name": "NANO UREA",
    "Category": "NANO FERTILIZER",
    "GST (%)": 5,
    "HSN": "31051000",
    "Batch no.": "----",
    "Quantity (total number)": 60,
    "Measurement type": "ML",
    "Unit Capacity (weight/volume)": 500,
    "Taxable Unit Amount": 194.28,
    "Taxable Total Amount": 11656.8,
    "Total Amount (Incl. GST)": 12239.64
  }
]

def parse_date(date_str):
    """
    Safely parse date from string. Supported formats:
    DD.MM.YYYY, DD/MM/YYYY, DD-MM-YYYY, YYYY-MM-DD
    If date is null or '---', returns today's date and a warning flag.
    """
    if not date_str or str(date_str).strip() in ["---", "null", "None", ""]:
        return timezone.now().date(), True

    date_str = str(date_str).strip()
    formats = ['%d.%m.%Y', '%d/%m/%Y', '%d-%m-%Y', '%Y-%m-%d', '%d.%m.%y', '%d-%m-%y']
    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt).date(), False
        except ValueError:
            continue
    
    # Fallback to current date if parsing fails
    return timezone.now().date(), True

def map_measurement_type(m_type):
    """
    Normalize measurement type to model choices:
    kg, grams, liter, ml
    """
    m_type = str(m_type).strip().lower()
    mapping = {
        'kg': 'kg', 'kilogram': 'kg', 'kilograms': 'kg',
        'gm': 'grams', 'grams': 'grams', 'gram': 'grams',
        'ltr': 'liter', 'liter': 'liter', 'liters': 'liter',
        'ml': 'ml', 'milliliter': 'ml', 'milliliters': 'ml'
    }
    return mapping.get(m_type, 'kg')

def safe_decimal(value):
    """Safely convert value to Decimal."""
    try:
        if value is None or str(value).strip() == "":
            return Decimal("0.00")
        return Decimal(str(value).strip().replace(',', ''))
    except (InvalidOperation, ValueError, TypeError):
        return Decimal("0.00")

def load_products():
    """
    Main function to load products into the database.
    Matches UI behavior and logic.
    """
    print(f"--- Starting Product Import: {len(PRODUCT_DATA)} records found ---")
    
    # Get the first active store owner/user to assign products to
    # In a multi-tenant app, usually you'd specify a user, but here we pick the first admin-like user
    owner = CustomUser.objects.filter(is_active=True).first()
    if not owner:
        print("CRITICAL ERROR: No active CustomUser found in the database. Please create a user first.")
        return

    print(f"Assigning products to user: {owner.username}\n")

    success_count = 0
    failed_count = 0
    failures = []

    for idx, item in enumerate(PRODUCT_DATA, 1):
        try:
            # Strip extra spaces from string inputs
            p_name = str(item.get("Product name", "")).strip()
            p_invoice = str(item.get("Purchase invoice number", "")).strip()
            
            # Date handling
            p_date_raw = item.get("Purchase date")
            p_date, is_default_date = parse_date(p_date_raw)
            
            # Measurement normalize
            m_type = map_measurement_type(item.get("Measurement type", "kg"))
            
            # Numeric conversion safely
            qty_raw = item.get("Quantity (total number)", 0)
            qty = int(float(str(qty_raw).strip() or 0))
            
            unit_cap = safe_decimal(item.get("Unit Capacity (weight/volume)", 1))
            tax_unit_amt = safe_decimal(item.get("Taxable Unit Amount", 0))
            tax_total_amt = safe_decimal(item.get("Taxable Total Amount", 0))
            total_grand_amt = safe_decimal(item.get("Total Amount (Incl. GST)", 0))
            gst_rate = safe_decimal(item.get("GST (%)", 0))
            
            # In the project UI, 'price' in the Product model is the GST-inclusive price per unit/pack
            # Logic: Total Grand Amount / Quantity
            unit_total_price = Decimal("0.00")
            if qty > 0:
                unit_total_price = total_grand_amt / Decimal(str(qty))
            
            # Create the Product record (Always new, No duplicates check)
            product = Product.objects.create(
                store_owner=owner,
                purchased_from=str(item.get("Company name (purchased from)", "")).strip(),
                company_gstin=str(item.get("Company GSTIN", "")).strip()[:15],
                purchase_date=p_date,
                purchase_invoice_number=p_invoice,
                name=p_name,
                category=str(item.get("Category", "General")).strip(),
                gst=gst_rate,
                hsn_code=str(item.get("HSN", "")).strip(),
                batch_number=str(item.get("Batch no.", "")).strip(),
                quantity=qty,
                initial_stock=qty,
                measurement_type=m_type,
                unit_capacity=unit_cap,
                unit_value=unit_cap, # Compatibility field for old logic
                taxable_unit_amount=tax_unit_amt,
                taxable_total_amount=tax_total_amt,
                total_amount=total_grand_amt,
                # Compatibility fields (AD Section uses these)
                unit_amount=tax_unit_amt, 
                net_amount=qty * tax_unit_amt,
                # The 'price' used in storefront (Cart/Checkout)
                price=unit_total_price,
                image=None # No image as per requirement No. 10
            )
            
            success_count += 1
            log_msg = f"[{idx}] Success: {p_name} | Invoice: {p_invoice}"
            if is_default_date:
                log_msg += " (Used Default Date)"
            print(log_msg)

        except Exception as e:
            failed_count += 1
            fail_info = {
                "name": item.get("Product name", "Unknown"),
                "invoice": item.get("Purchase invoice number", "Unknown"),
                "error": str(e)
            }
            failures.append(fail_info)
            print(f"[{idx}] FAILED: {fail_info['name']} - {fail_info['error']}")

    # Final summary output (Mandatory Logging Output)
    print("\n" + "="*50)
    print("IMPORT COMPLETE - SUMMARY")
    print("="*50)
    print(f"Total processed:      {len(PRODUCT_DATA)}")
    print(f"Successfully added:   {success_count}")
    print(f"Failed records:       {failed_count}")
    
    if failed_count > 0:
        print("\n--- FAILURE RECORD DETAILS ---")
        for f in failures:
            print(f"Product: {f['name']} | Invoice: {f['invoice']}")
            print(f"Error:   {f['error']}")
            print("-" * 30)
    print("="*50)

if __name__ == "__main__":
    load_products()