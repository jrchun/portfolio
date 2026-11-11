"""web/symbols.json 재생성 스크립트 (종목 검색용 목록).

사용법: python3 scripts/build_symbols.py <원본 폴더> web/symbols.json
원본 폴더에 아래 자료를 미리 받아 둔다.
  reg/  ← git clone https://github.com/pon00050/kr-company-registry   (국내 상장사: data/dist/kr_corp_ids.csv)
  ds/   ← git clone https://github.com/gottso/darren-scan              (kr_etfs.csv, us_etfs.csv)
  mc/   ← git clone https://github.com/FinanceData/marcap              (data/marcap-<연도>.parquet, 국내 시가총액)
  us_nasdaq.json, us_nyse.json, us_amex.json
        ← https://raw.githubusercontent.com/rreichel3/US-Stock-Symbols/main/<거래소>/<거래소>_full_tickers.json
필요 패키지: pandas, pyarrow
출력 행 형식: [코드, 이름, 상장구분, 시가총액(억원), 별칭('|' 구분), 보조순위, 자산군]
  상장구분: KS 국내주식 / KE 국내ETF / US 미국주식 / UE 미국ETF / GD KRX 금현물 / CR 코인
  자산군:   KS 국내주식 / GS 해외주식 / BD 채권 / CM 금·원자재 / RE 리츠·부동산 / CA 현금성 / CR 가상자산
주의: marcap 파일 연도(2026)와 환율 가정(FX=1400)은 코드에 고정돼 있다. 해가 바뀌면 고친다.
"""
from collections import Counter
import csv, json, re, sys
dl = sys.argv[1]; out = sys.argv[2]

CASH_KR = re.compile(r'달러선물|달러SOFR|엔선물|머니마켓|MMF|CD금리|KOFR|SOFR|단기자금|초단기|단기통안|파킹|금리액티브|머니|단기채권액티브')
BOND_KR = re.compile(r'채권|국채|국고채|회사채|크레딧|통안|은행채|금융채|미국채|TIPS|물가채|장기채|중기채|단기채|국공채|하이일드|크레딧')
CMDTY_KR = re.compile(r'금현물|골드|금선물|KRX금|금액티브|은선물|실버|원유|WTI|구리|원자재|농산물|천연가스|귀금속|팔라듐|백금')
REIT_KR = re.compile(r'리츠|부동산|REIT')
CRYPTO_KR = re.compile(r'비트코인|이더리움|가상자산')
FOREIGN_KR = re.compile(r'미국|글로벌|S&P|나스닥|NASDAQ|필라델피아|다우|중국|차이나|일본|니케이|인도|베트남|유럽|선진|신흥|MSCI|테슬라|엔비디아|애플|마이크로소프트|구글|아마존|메타|빅테크|월드|대만|홍콩|항셍|브라질|멕시코|독일|인도네시아|팔란티어|브로드컴|TSMC|ASML|ACWI|FANG|매그니피센트|인공지능|AI테크')
def kr_etf_class(name, cat):
    if CRYPTO_KR.search(name): return 'CR'
    if CASH_KR.search(name): return 'CA'
    if BOND_KR.search(name) or cat == '채권/금리': return 'BD'
    if CMDTY_KR.search(name) or cat == '원자재/에너지' and re.search(r'선물|원유|가스', name): return 'CM'
    if REIT_KR.search(name) or cat == '부동산/리츠': return 'RE'
    if FOREIGN_KR.search(name) or cat == '국가/신흥': return 'GS'
    return 'KS'
CASH_US = re.compile(r'0-3 Month|1-3 Month|0-1 Year|T-Bill|Treasury Bill|Money Market|Ultra.?Short|Floating Rate|Short Treasury|Cash', re.I)
CMDTY_US = re.compile(r'Gold|Silver|Oil|Commodit|Copper|Platinum|Palladium|Natural Gas|Crude|Agricultur|Precious', re.I)
EQUITY_HINT = re.compile(r'Miners|Equity|Producers|Select Sector|Companies|Stocks', re.I)
def us_etf_class(name, cat):
    if cat == '크립토' or re.search(r'Bitcoin|Ether|Crypto|Solana|XRP', name, re.I): return 'CR'
    if CASH_US.search(name): return 'CA'
    if cat == '채권/금리' or re.search(r'Bond|Treasury|Muni|Fixed Income|Credit|TIPS|Corporate|Aggregate', name, re.I): return 'BD'
    if (cat in ('귀금속', '원자재/에너지') or CMDTY_US.search(name)) and not EQUITY_HINT.search(name) and CMDTY_US.search(name): return 'CM'
    if cat == '부동산/리츠' or re.search(r'Real Estate|REIT', name, re.I): return 'RE'
    return 'GS'

rows = []  # [code, name, type, cap(억원, 0=unknown), alias, secondary]
import pandas as pd
_m = pd.read_parquet(f'{dl}/mc/data/marcap-2026.parquet'); _m = _m[_m['Date']==_m['Date'].max()]
CAP = {r.Code: r.Marcap for r in _m.itertuples()}
CAP_DATE = str(_m['Date'].max())[:10]
FX = 1400
# KR stocks
for r in csv.DictReader(open(f'{dl}/reg/data/dist/kr_corp_ids.csv', encoding='utf-8-sig')):
    if r['is_listed'] != 'True' or not r['ticker'] or r['market'] not in ('KOSPI','KOSDAQ','KONEX'): continue
    cap = CAP.get(r['ticker'], 0) or 0
    rows.append([r['ticker'], r['corp_name'], 'KS', round(cap/1e8), '', 0, 'RE' if '리츠' in r['corp_name'] else 'KS'])
# KR ETFs
for r in csv.DictReader(open(f'{dl}/ds/kr_etfs.csv', encoding='utf-8-sig')):
    code = r['ticker'].split('.')[0]
    try: adv = float(r['krx_advol_억'] or 0)
    except: adv = 0
    rows.append([code, r['name'], 'KE', 0, '', round(adv, 1), kr_etf_class(r['name'], r['category'])])
# US stocks
alias = {'AAPL':'애플','MSFT':'마이크로소프트','NVDA':'엔비디아','GOOGL':'구글|알파벳','GOOG':'구글|알파벳','AMZN':'아마존','META':'메타|페이스북','TSLA':'테슬라','AVGO':'브로드컴','BRK.B':'버크셔해서웨이','JPM':'제이피모건','V':'비자','MA':'마스터카드','LLY':'일라이릴리','UNH':'유나이티드헬스','XOM':'엑슨모빌','JNJ':'존슨앤존슨','WMT':'월마트','PG':'프록터앤갬블','COST':'코스트코','HD':'홈디포','KO':'코카콜라','PEP':'펩시','MCD':'맥도날드','NFLX':'넷플릭스','DIS':'디즈니','ADBE':'어도비','CRM':'세일즈포스','ORCL':'오라클','AMD':'에이엠디','INTC':'인텔','QCOM':'퀄컴','TXN':'텍사스인스트루먼트','MU':'마이크론','ASML':'에이에스엠엘','TSM':'TSMC|대만반도체','PLTR':'팔란티어','SBUX':'스타벅스','NKE':'나이키','BA':'보잉','IBM':'아이비엠','CSCO':'시스코','ABBV':'애브비','MRK':'머크','PFE':'화이자','T':'에이티앤티','VZ':'버라이즌','O':'리얼티인컴','ARM':'에이알엠','SMCI':'슈퍼마이크로','COIN':'코인베이스','MSTR':'마이크로스트래티지|스트래티지','UBER':'우버','ABNB':'에어비앤비','SHOP':'쇼피파이','PYPL':'페이팔','BAC':'뱅크오브아메리카','GS':'골드만삭스','CVX':'쉐브론','IONQ':'아이온큐','RKLB':'로켓랩','SOFI':'소파이','HOOD':'로빈후드','CPNG':'쿠팡','ISRG':'인튜이티브서지컬','NVO':'노보노디스크','PM':'필립모리스','MO':'알트리아','LMT':'록히드마틴','CAT':'캐터필러','GE':'지이','AMAT':'어플라이드머티리얼즈','LRCX':'램리서치','PANW':'팔로알토','CRWD':'크라우드스트라이크','SNOW':'스노우플레이크','DELL':'델','ANET':'아리스타','VRT':'버티브','CEG':'컨스텔레이션에너지','OKLO':'오클로','SPGI':'S&P글로벌'}
clean = re.compile(r'\s+(Class [A-C] )?(Common Stock|Ordinary Shares|American Depositary Shares|Common Shares|Depositary Shares).*$', re.I)
seen = set()
for ex in ('nasdaq','nyse','amex'):
    for r in json.load(open(f'{dl}/us_{ex}.json')):
        sym = r['symbol'].replace('/', '.').strip()
        try: mc = float(r.get('marketCap') or 0)
        except: mc = 0
        if mc < 1e9 or sym in seen or '^' in sym: continue
        seen.add(sym)
        name = clean.sub('', r['name']).strip() or r['name']
        rows.append([sym, name, 'US', round(mc*FX/1e8), alias.get(sym, ''), 0, 'RE' if 'Real Estate Investment' in (r.get('industry') or '') else 'GS'])
# US ETFs (popular)
etfs = [('SPY','SPDR S&P 500','S&P500'),('VOO','Vanguard S&P 500','S&P500'),('IVV','iShares Core S&P 500','S&P500'),('SPLG','SPDR Portfolio S&P 500','S&P500'),('QQQ','Invesco QQQ (Nasdaq-100)','나스닥100'),('QQQM','Invesco Nasdaq 100','나스닥100'),('TQQQ','ProShares UltraPro QQQ (3x)','나스닥 3배'),('SQQQ','ProShares UltraPro Short QQQ','나스닥 인버스'),('VTI','Vanguard Total Stock Market','미국전체'),('SCHD','Schwab US Dividend Equity','배당 슈드'),('JEPI','JPMorgan Equity Premium Income','커버드콜 배당'),('JEPQ','JPMorgan Nasdaq Equity Premium Income','커버드콜 배당'),('DIA','SPDR Dow Jones Industrial Average','다우'),('IWM','iShares Russell 2000','러셀 소형주'),('VUG','Vanguard Growth','성장주'),('SCHG','Schwab US Large-Cap Growth','성장주'),('VGT','Vanguard Information Technology','기술주'),('XLK','Technology Select Sector SPDR','기술주'),('SOXX','iShares Semiconductor','반도체'),('SMH','VanEck Semiconductor','반도체'),('SOXL','Direxion Daily Semiconductor Bull 3x','반도체 3배'),('XLF','Financial Select Sector SPDR','금융'),('XLE','Energy Select Sector SPDR','에너지'),('XLV','Health Care Select Sector SPDR','헬스케어'),('XLU','Utilities Select Sector SPDR','유틸리티'),('VYM','Vanguard High Dividend Yield','고배당'),('DGRO','iShares Core Dividend Growth','배당성장'),('VIG','Vanguard Dividend Appreciation','배당성장'),('DIVO','Amplify CWP Enhanced Dividend Income','배당'),('VNQ','Vanguard Real Estate','리츠'),('VEA','Vanguard FTSE Developed Markets','선진국'),('VWO','Vanguard FTSE Emerging Markets','신흥국'),('VXUS','Vanguard Total International Stock','미국외'),('VT','Vanguard Total World Stock','전세계'),('EFA','iShares MSCI EAFE','선진국'),('EEM','iShares MSCI Emerging Markets','신흥국'),('INDA','iShares MSCI India','인도'),('EWJ','iShares MSCI Japan','일본'),('TLT','iShares 20+ Year Treasury Bond','미국 장기채'),('TMF','Direxion Daily 20+ Yr Treasury Bull 3x','장기채 3배'),('IEF','iShares 7-10 Year Treasury Bond','미국 중기채'),('SHY','iShares 1-3 Year Treasury Bond','미국 단기채'),('BIL','SPDR Bloomberg 1-3 Month T-Bill','초단기채'),('SGOV','iShares 0-3 Month Treasury Bond','초단기채'),('BND','Vanguard Total Bond Market','미국채권'),('AGG','iShares Core US Aggregate Bond','미국채권'),('LQD','iShares iBoxx Investment Grade Corporate Bond','회사채'),('HYG','iShares iBoxx High Yield Corporate Bond','하이일드'),('TIP','iShares TIPS Bond','물가연동채'),('GLD','SPDR Gold Shares','금'),('IAU','iShares Gold Trust','금'),('GLDM','SPDR Gold MiniShares','금'),('SLV','iShares Silver Trust','은'),('DBC','Invesco DB Commodity Index','원자재'),('IBIT','iShares Bitcoin Trust','비트코인 현물'),('FBTC','Fidelity Wise Origin Bitcoin','비트코인 현물'),('ETHA','iShares Ethereum Trust','이더리움 현물'),('ARKK','ARK Innovation','아크 혁신'),('XLY','Consumer Discretionary Select Sector SPDR','경기소비재'),('XLP','Consumer Staples Select Sector SPDR','필수소비재'),('XLI','Industrial Select Sector SPDR','산업재'),('RSP','Invesco S&P 500 Equal Weight','동일가중'),('MOAT','VanEck Morningstar Wide Moat','해자'),('QYLD','Global X Nasdaq 100 Covered Call','커버드콜'),('SCHB','Schwab US Broad Market','미국전체'),('SPYM','SPDR Portfolio S&P 500','S&P500'),('UPRO','ProShares UltraPro S&P500 (3x)','S&P500 3배'),('URA','Global X Uranium','우라늄'),('ITA','iShares US Aerospace & Defense','방산')]
US_CAT = {r['ticker'].strip(): r['category'] for r in csv.DictReader(open(f'{dl}/ds/us_etfs.csv', encoding='utf-8-sig'))}
for i,(sym, name, al) in enumerate(etfs):
    if sym in seen: continue
    seen.add(sym); rows.append([sym, name, 'UE', 0, al, 1000 - i, us_etf_class(name, US_CAT.get(sym, ''))])
for r in csv.DictReader(open(f'{dl}/ds/us_etfs.csv', encoding='utf-8-sig')):
    sym = r['ticker'].strip()
    if not sym or sym in seen: continue
    seen.add(sym); rows.append([sym, r['name'].strip(), 'UE', 0, '', 0, us_etf_class(r['name'], r['category'])])
# Gold & coins
rows.append(['M04020000', 'KRX 금현물 (1g)', 'GD', 0, '금|금현물|골드|gold', 2000, 'CM'])
coins = [('BTC','비트코인','bitcoin'),('ETH','이더리움','ethereum'),('XRP','엑스알피(리플)','ripple'),('SOL','솔라나','solana'),('DOGE','도지코인','dogecoin'),('TRX','트론','tron'),('ADA','에이다(카르다노)','cardano'),('LINK','체인링크','chainlink'),('AVAX','아발란체','avalanche'),('SUI','수이','sui')]
for i,(c,n,e) in enumerate(coins):
    rows.append(['KRW-'+c, n, 'CR', 0, c+'|'+e, 10-i, 'CR'])
json.dump(rows, open(out,'w'), ensure_ascii=False, separators=(',',':'))
print(Counter(r[6] for r in rows)); print(CAP_DATE, len(rows), sum(1 for r in rows if r[2]=='KS' and r[3]==0), 'KS no cap', Counter(r[2] for r in rows), round(len(open(out,encoding='utf-8').read().encode())/1024), 'KB')
