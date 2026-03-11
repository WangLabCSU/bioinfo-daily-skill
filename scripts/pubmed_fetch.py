#!/usr/bin/env python3
"""
Bioinfo Daily - PubMed 文献日报生成器 v3.0
数据获取 + AI 智能分析模式
脚本只负责获取数据，分类和标注由AI完成
"""

import requests
import json
from datetime import datetime, timedelta
from typing import List, Dict
import xml.etree.ElementTree as ET
import os

# 环境变量配置
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SKILL_DIR = os.path.dirname(SCRIPT_DIR)
ENV_FILE = os.path.join(SKILL_DIR, '.env')

if os.path.exists(ENV_FILE):
    with open(ENV_FILE, 'r') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                if key not in os.environ:
                    os.environ[key] = value

NCBI_EMAIL = os.environ.get("NCBI_EMAIL", "your@email.com")
NCBI_API_KEY = os.environ.get("NCBI_API_KEY", "")
BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

# 搜索关键词配置（更宽泛，交给AI分类）
SEARCH_TOPICS = [
    ("(cancer[Title/Abstract] OR tumor[Title/Abstract] OR carcinoma[Title/Abstract] OR neoplasm[Title/Abstract]) AND (bioinformatics[Title/Abstract] OR computational[Title/Abstract] OR algorithm[Title/Abstract] OR 'machine learning'[Title/Abstract] OR AI[Title/Abstract])", "计算生物学相关"),
    ("(cancer[Title/Abstract] OR tumor[Title/Abstract]) AND (immunotherapy[Title/Abstract] OR immune[Title/Abstract] OR checkpoint[Title/Abstract] OR CAR-T[Title/Abstract] OR T cell[Title/Abstract])", "肿瘤免疫相关"),
    ("(cancer[Title/Abstract] OR tumor[Title/Abstract]) AND (single-cell[Title/Abstract] OR single cell[Title/Abstract] OR scRNA[Title/Abstract])", "单细胞测序相关"),
    ("(cancer[Title/Abstract] OR tumor[Title/Abstract]) AND (spatial[Title/Abstract] OR VISIUM[Title/Abstract] OR spatial transcriptomics[Title/Abstract])", "空间组学相关"),
    ("(cancer[Title/Abstract] OR tumor[Title/Abstract]) AND (clinical[Title/Abstract] OR therapeutic[Title/Abstract] OR treatment[Title/Abstract] OR trial[Title/Abstract])", "临床治疗相关"),
]

# 高影响力期刊列表
HIGH_IMPACT_JOURNALS = {
    "Nature", "Science", "Cell", "Nature Medicine", "Nature Genetics", 
    "Nature Biotechnology", "Nature Immunology", "Nature Cancer", "Nature Communications",
    "Nature Reviews Cancer", "Nature Reviews Clinical Oncology",
    "Science Translational Medicine", "Science Immunology", "Science Advances",
    "Cell Research", "Cell Metabolism", "Cell Stem Cell", "Cancer Cell", "Immunity",
    "PNAS", "Proceedings of the National Academy of Sciences",
    "The Lancet", "The Lancet Oncology", "JAMA", "JAMA Oncology",
    "Cell Discovery", "Advanced Science", "Cell Reports", "Genome Biology",
    "Cancer Research", "Clinical Cancer Research", "Journal of Clinical Oncology",
    "Blood", "Leukemia", "Gut", "Hepatology", "Gastroenterology"
}

def get_yesterday_date() -> str:
    yesterday = datetime.now() - timedelta(days=1)
    return yesterday.strftime("%Y/%m/%d")

def search_pubmed(query: str, date: str, max_results: int = 100) -> List[str]:
    date_query = f"({query}) AND ({date}[PDAT])"
    search_url = f"{BASE_URL}/esearch.fcgi"
    params = {
        "db": "pubmed", "term": date_query, "retmax": max_results,
        "retmode": "json", "sort": "date",
        "email": NCBI_EMAIL, "api_key": NCBI_API_KEY,
    }
    try:
        response = requests.get(search_url, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()
        return data.get("esearchresult", {}).get("idlist", [])
    except Exception as e:
        print(f"搜索失败: {e}")
        return []

def fetch_article_details(pmids: List[str]) -> List[Dict]:
    if not pmids:
        return []
    
    fetch_url = f"{BASE_URL}/efetch.fcgi"
    params = {
        "db": "pubmed", "id": ",".join(pmids),
        "retmode": "xml", "email": NCBI_EMAIL, "api_key": NCBI_API_KEY,
    }
    
    try:
        response = requests.get(fetch_url, params=params, timeout=30)
        response.raise_for_status()
        root = ET.fromstring(response.content)
        articles = []
        
        for article in root.findall(".//PubmedArticle"):
            try:
                title = article.find(".//ArticleTitle").text or "N/A"
                journal = article.find(".//Journal/Title").text or "N/A"
                
                abstract_elems = article.findall(".//Abstract/AbstractText")
                abstract = " ".join([e.text for e in abstract_elems if e.text]) or "N/A"
                
                author_elems = article.findall(".//Author/LastName")
                first_author = author_elems[0].text if author_elems else "N/A"
                
                year = article.find(".//PubDate/Year").text if article.find(".//PubDate/Year") is not None else "N/A"
                pmid = article.find(".//PMID").text or "N/A"
                doi = article.find(".//ArticleId[@IdType='doi']").text if article.find(".//ArticleId[@IdType='doi']") is not None else "N/A"
                
                articles.append({
                    "pmid": pmid,
                    "title": title,
                    "journal": journal,
                    "abstract": abstract[:1000] + "..." if len(abstract) > 1000 else abstract,
                    "first_author": first_author,
                    "year": year,
                    "doi": doi,
                    "pubmed_url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
                })
            except:
                continue
        return articles
    except Exception as e:
        print(f"获取详情失败: {e}")
        return []

def filter_high_impact(articles: List[Dict]) -> List[Dict]:
    filtered = []
    for article in articles:
        journal = article.get("journal", "")
        for tier in HIGH_IMPACT_JOURNALS:
            if tier.lower() in journal.lower():
                article["journal_tier"] = "High Impact"
                filtered.append(article)
                break
    return filtered

def main():
    print("🔬 正在获取PubMed文献数据...\n")
    
    yesterday = get_yesterday_date()
    print(f"📅 搜索日期: {yesterday}\n")
    
    all_articles = []
    
    for query, topic in SEARCH_TOPICS:
        print(f"搜索: {topic}...")
        pmids = search_pubmed(query, yesterday, max_results=50)
        if pmids:
            articles = fetch_article_details(pmids)
            filtered = filter_high_impact(articles)
            for art in filtered:
                art["search_source"] = topic
            all_articles.extend(filtered)
            print(f"  ✓ {len(filtered)} 篇高影响力文献")
        import time
        time.sleep(0.5)
    
    # 去重
    unique = {a["pmid"]: a for a in all_articles}
    articles = list(unique.values())
    
    print(f"\n📊 总计: {len(articles)} 篇高影响力文献\n")
    
    # 保存原始数据（JSON格式，供AI分析）
    import json
    output_file = f"/tmp/bioinfo_raw_{yesterday.replace('/', '')}.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump({
            "date": yesterday,
            "total": len(articles),
            "articles": articles
        }, f, ensure_ascii=False, indent=2)
    
    print(f"📄 原始数据已保存: {output_file}")
    print(f"💡 请使用 read 工具读取该文件，然后由AI进行智能分类和亮点标注\n")
    
    return output_file

if __name__ == "__main__":
    main()
PYEOF
print("Script v3.0 created!")