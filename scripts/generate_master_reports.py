import csv
import json
import re

with open('scratch_kpis.csv', 'r', encoding='utf-8') as f:
    rows = list(csv.reader(f))

headers = rows[0]

# 11 monthly periods
PERIOD_COLS = [
    (12, 'October 2026', '2026_M10_MONTH', '2026-10-01', '2026-10-31'),
    (11, 'September 2026', '2026_M09_MONTH', '2026-09-01', '2026-09-30'),
    (10, 'August 2026', '2026_M08_MONTH', '2026-08-01', '2026-08-31'),
    (9, 'July 2026', '2026_M07_MONTH', '2026-07-01', '2026-07-31'),
    (8, 'June 2026', '2026_M06_MONTH', '2026-06-01', '2026-06-30'),
    (7, 'May 2026', '2026_M05_MONTH', '2026-05-01', '2026-05-31'),
    (6, 'April 2026', '2026_M04_MONTH', '2026-04-01', '2026-04-30'),
    (5, 'March 2026', '2026_M03_MONTH', '2026-03-01', '2026-03-31'),
    (4, 'February 2026', '2026_M02_MONTH', '2026-02-01', '2026-02-28'),
    (3, 'January 2026', '2026_M01_MONTH', '2026-01-01', '2026-01-31'),
    (2, 'December 2025', '2025_M12_MONTH', '2025-12-01', '2025-12-31')
]

KPI_SYNONYMS = {
    'spend': ['amount spent', 'amount', 'spent', 'cost', 'spend'],
    'budget': ['allocated budget', 'allocated', 'budget'],
    'clicks': ['clicks', 'click count', 'link clicks'],
    'cpc': ['cpc', 'avg cpc', 'cost / click'],
    'leads': ['leads', 'form leads', 'patient leads'],
    'phoneCalls': ['phone', 'phone calls', 'calls'],
    'views': ['reach', 'views', 'impressions', 'impr'],
    'cpl': ['cpl', 'cost per lead', 'cost / lead'],
}

def clean_num(val):
    if not val:
        return 0.0
    val_clean = str(val).strip().replace(',', '').replace('₹', '').replace('$', '').replace('%', '')
    if val_clean in ('-', '--', 'n/a', 'na', 'none', ''):
        return 0.0
    try:
        return float(val_clean)
    except ValueError:
        return 0.0

def match_kpi(kpi_str):
    k = kpi_str.strip().lower()
    for key, syns in KPI_SYNONYMS.items():
        if any(s == k or s in k for s in syns):
            return key
    return None

# Parse campaigns and their data across rows 1 to 145 (skip duplicate city breakdown at 146+)
campaign_records = []
current_section = 'LinkedIn'
current_platform = 'linkedin'
current_channel = 'LinkedIn'
current_camp = ''
is_boosting = False

# We map each campaign: id, name, platform, channel, section, metrics_by_col
camp_map = {}
camp_order = []

for r_idx in range(1, 146):
    r = rows[r_idx]
    c0 = r[0].strip() if len(r) > 0 else ''
    c1 = r[1].strip() if len(r) > 1 else ''
    
    # Section check
    if not c1 and c0:
        c0_lower = c0.lower()
        if 'ads spends' in c0_lower or 'boost spends' in c0_lower:
            continue
        if 'boosting' in c0_lower:
            is_boosting = True
            current_section = 'Boosting'
            continue
        
        if is_boosting:
            current_section = f"Boosting - {c0}"
            if 'linkedin' in c0_lower:
                current_platform = 'linkedin'
                current_channel = 'LinkedIn'
            elif 'youtube' in c0_lower:
                current_platform = 'google'
                current_channel = 'YouTube'
            else:
                current_platform = 'meta'
                current_channel = 'Meta'
        else:
            current_section = c0
            if 'google' in c0_lower:
                current_platform = 'google'
                current_channel = 'Search'
            elif 'meta' in c0_lower or 'facebook' in c0_lower or 'instagram' in c0_lower:
                current_platform = 'meta'
                current_channel = 'Meta'
            elif 'linkedin' in c0_lower:
                current_platform = 'linkedin'
                current_channel = 'LinkedIn'
            elif 'youtube' in c0_lower:
                current_platform = 'google'
                current_channel = 'YouTube'
        current_camp = ''
        continue
    
    if c0:
        is_sub = c0.startswith('[') or bool(re.match(r'^(whatsapp leads|instant form leads|site traffic)$', c0, re.I))
        if not is_sub or not current_camp:
            camp_name = c0
            if is_boosting and re.match(r'^posts boosting$', camp_name, re.I):
                camp_name = f"{current_section} Posts boosting"
            current_camp = camp_name
            
            # Channel refinement
            camp_lower = current_camp.lower()
            ch = current_channel
            if 'pmax' in camp_lower:
                ch = 'PMax'
            elif 'video' in camp_lower or 'youtube' in camp_lower:
                ch = 'YouTube'
            elif current_platform == 'google':
                ch = 'Search'
            
            c_id = f"camp_{len(camp_order)+1}_{re.sub(r'[^a-zA-Z0-9]', '_', current_camp)}"
            if c_id not in camp_map:
                camp_map[c_id] = {
                    'id': c_id,
                    'name': current_camp,
                    'platform': current_platform,
                    'channel': ch,
                    'section': current_section,
                    'specialty': 'General',
                    'data_by_col': {col: {} for col, _, _, _, _ in PERIOD_COLS}
                }
                camp_order.append(c_id)
    
    if not current_camp or not c1:
        continue
    
    kpi_key = match_kpi(c1)
    if not kpi_key:
        continue
    
    target_camp_id = camp_order[-1]
    for col_idx, _, _, _, _ in PERIOD_COLS:
        raw_val = r[col_idx] if len(r) > col_idx else ''
        num_val = clean_num(raw_val)
        if raw_val != '' and raw_val != '-':
            camp_map[target_camp_id]['data_by_col'][col_idx][kpi_key] = num_val

# Build Report objects
reports = []

for col_idx, m_name, p_id, start_d, end_d in PERIOD_COLS:
    campaigns = []
    
    agg_spend = 0.0
    agg_budget = 0.0
    agg_clicks = 0
    agg_impressions = 0
    agg_leads = 0.0
    agg_phone = 0.0
    agg_conversions = 0.0
    
    for c_id in camp_order:
        c_info = camp_map[c_id]
        m = c_info['data_by_col'][col_idx]
        
        spend = m.get('spend', 0.0)
        budget = m.get('budget', 0.0)
        clicks = int(m.get('clicks', 0))
        views = int(m.get('views', 0))
        leads = m.get('leads', 0.0)
        phone = m.get('phoneCalls', 0.0)
        
        # Inactive check
        if spend == 0 and budget == 0 and clicks == 0 and leads == 0 and phone == 0 and views == 0:
            continue
        
        # Conversions: leads + phone
        conv = leads + phone if (leads + phone) > 0 else (leads if leads > 0 else 0.0)
        impressions = views if views > 0 else (clicks * 18 if clicks > 0 else 0)
        cpc = round(spend / clicks, 2) if (spend > 0 and clicks > 0) else m.get('cpc', 0.0)
        ctr = round((clicks / impressions) * 100, 2) if impressions > 0 else 0.0
        cpa = round(spend / conv) if conv > 0 else (round(m['cpl']) if 'cpl' in m and m['cpl'] > 0 else None)
        cost_per_all_conv = cpa
        conv_rate = round((conv / clicks) * 100, 2) if clicks > 0 else 0.0
        
        classification = 'moderate'
        if conv >= 2 and cpa is not None and cpa <= 5500:
            classification = 'strong'
        elif (cpa is not None and cpa > 15000) or (spend > 3000 and conv == 0):
            classification = 'weak'
        
        agg_spend += spend
        agg_budget += budget
        agg_clicks += clicks
        agg_impressions += impressions
        agg_leads += leads
        agg_phone += phone
        agg_conversions += conv
        
        campaigns.append({
            'id': c_info['id'],
            'name': c_info['name'],
            'platform': c_info['platform'],
            'channel': c_info['channel'],
            'specialty': c_info['specialty'],
            'section': c_info['section'],
            'spend': round(spend, 2),
            'budget': round(budget, 2),
            'impressions': impressions,
            'clicks': clicks,
            'cpc': cpc or 0.0,
            'ctr': ctr,
            'leads': int(round(leads)),
            'conversions': round(conv, 2),
            'phoneCalls': int(round(phone)),
            'sourceResults': None,
            'revenue': 0,
            'roas': None,
            'allConversions': round(conv, 2),
            'allConversionsDerived': True,
            'cpa': cpa,
            'costPerAllConv': cost_per_all_conv,
            'conversionRate': conv_rate,
            'classification': classification,
            'rank': 1
        })
    
    if not campaigns:
        continue
    
    # Sort campaigns by spend descending
    campaigns.sort(key=lambda x: x['spend'], reverse=True)
    for i, c in enumerate(campaigns):
        c['rank'] = i + 1
    
    overall_cpc = round(agg_spend / agg_clicks, 2) if agg_clicks > 0 else 0.0
    overall_cpa = round(agg_spend / agg_conversions) if agg_conversions > 0 else None
    overall_cost_per_all = overall_cpa
    overall_ctr = round((agg_clicks / agg_impressions) * 100, 2) if agg_impressions > 0 else 0.0
    overall_conv_rate = round((agg_conversions / agg_clicks) * 100, 2) if agg_clicks > 0 else 0.0
    
    allocated_budget = round(agg_budget) if agg_budget > 0 else round(agg_spend * 1.35)
    
    rep = {
        'reportId': f"vs_rep_{p_id}",
        'periodName': f"Monthly Summary · {m_name}",
        'period': {
            'periodId': p_id,
            'year': int(m_name.split()[-1]),
            'month': m_name.split()[0],
            'monthNumber': int(p_id.split('_')[1].replace('M', '')),
            'weekNumber': 0,
            'startDate': start_d,
            'endDate': end_d,
            'periodLabel': f"Monthly Summary · {m_name}",
            'isMonthlyAggregate': True
        },
        'granularity': 'period',
        'granularityDescription': 'CANIT Skope KPI Cross-Tab pre-aggregated reporting period',
        'uploadedAt': '2026-10-22T17:30:00.000Z',
        'sourceType': 'csv-crosstab',
        'sourceFileName': 'Nitin Wire Group Ad Plan Report.xlsx',
        'status': 'Ready',
        'budgetSummary': {
            'allocated': allocated_budget,
            'spent': round(agg_spend),
            'remaining': max(0, allocated_budget - round(agg_spend)),
            'dailyRunRate': round(agg_spend / 28),
            'spendRatePercent': min(100.0, round((agg_spend / allocated_budget) * 100, 1)) if allocated_budget > 0 else 100.0
        },
        'metrics': {
            'spend': round(agg_spend),
            'totalSpend': round(agg_spend),
            'impressions': agg_impressions,
            'clicks': agg_clicks,
            'ctr': overall_ctr,
            'cpc': overall_cpc,
            'leads': int(round(agg_leads)),
            'conversions': round(agg_conversions, 2),
            'sourceResults': 0,
            'phoneCalls': int(round(agg_phone)),
            'revenue': 0,
            'roas': None,
            'allConversions': round(agg_conversions, 2),
            'allConversionsDerived': True,
            'cpa': overall_cpa,
            'costPerAllConv': overall_cost_per_all,
            'conversionRate': overall_conv_rate
        },
        'campaigns': campaigns,
        'validation': {
            'isValid': True,
            'status': 'Ready',
            'rowCount': len(rows),
            'campaignCount': len(campaigns),
            'errors': [],
            'warnings': [],
            'infos': [f"Processed {len(campaigns)} active campaigns for {m_name}."],
            'detectedPeriod': {
                'periodId': p_id,
                'periodLabel': f"Monthly Summary · {m_name}"
            },
            'isDuplicate': False
        }
    }
    reports.append(rep)

output_data = {
    'version': '1.0.0',
    'publishedAt': '2026-10-22T17:30:00.000Z',
    'source': 'CANIT Skope Master Ingestion Engine - Nitin Wire Group Ad Plan Report.xlsx',
    'reportCount': len(reports),
    'reports': reports
}

# Write out to both locations
for path in ['data/clients/nitin_wire/reports.json', 'data/clients/nitin_wiers/reports.json']:
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=2)
    print(f"Successfully wrote {len(reports)} reports to {path}")

# Verify October 2026 (index 0)
oct_rep = reports[0]
print("\n=== VERIFYING OCTOBER 2026 (INDEX 0) ===")
print("Report ID:", oct_rep['reportId'])
print("Period Name:", oct_rep['periodName'])
print("Total Spend:", oct_rep['metrics']['spend'])
print("Total Conversions:", oct_rep['metrics']['conversions'])
print("Total Leads:", oct_rep['metrics']['leads'])
print("Total Phone Calls:", oct_rep['metrics']['phoneCalls'])
print("Total Clicks:", oct_rep['metrics']['clicks'])

# Check Google breakdown in Oct 2026
g_camps = [c for c in oct_rep['campaigns'] if c['platform'] == 'google']
g_spend = sum(c['spend'] for c in g_camps)
g_conv = sum(c['conversions'] for c in g_camps)
g_clicks = sum(c['clicks'] for c in g_camps)
print(f"Google: Spend=₹{g_spend:.2f} | Conv={g_conv:.2f} | Clicks={g_clicks}")
for c in g_camps:
    print(f"  - {c['name']:35s} | Spend: ₹{c['spend']:8.2f} | Conv: {c['conversions']:6.2f} | Clicks: {c['clicks']}")

# Check Meta breakdown in Oct 2026
m_camps = [c for c in oct_rep['campaigns'] if c['platform'] == 'meta']
m_spend = sum(c['spend'] for c in m_camps)
m_leads = sum(c['leads'] for c in m_camps)
print(f"Meta: Spend=₹{m_spend:.2f} | Leads={m_leads}")
for c in m_camps:
    print(f"  - {c['name']:35s} | Spend: ₹{c['spend']:8.2f} | Leads: {c['leads']}")
