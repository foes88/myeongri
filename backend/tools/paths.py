"""경로 상수. data_private/ 는 .gitignore 대상이며 이용 조건이 불명확한 외부 원자료·파생 대량 자료를 둔다(공개 저장소 금지)."""
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
GOLDEN = BACKEND / "golden"
PRIVATE = BACKEND / "data_private"
EXTERNAL = PRIVATE / "external"
HKO_FILE = EXTERNAL / "hko_lunar_terms.json"
KASI_FILE = EXTERNAL / "kasi_calendar.json"
EXT_CASES = PRIVATE / "cases_external.json"
EXT_REPORT = PRIVATE / "report_external.json"
EXT_TERM_ANALYSIS = PRIVATE / "term_analysis_full.json"
