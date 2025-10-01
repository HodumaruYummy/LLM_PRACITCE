import streamlit as st
import requests
import json
import pandas as pd
from datetime import datetime, timedelta
import re
from typing import List, Dict
import time
import plotly.express as px
import plotly.graph_objects as go
from wordcloud import WordCloud
import matplotlib.pyplot as plt
from io import BytesIO
import base64

# 페이지 설정
st.set_page_config(
    page_title="뉴스 기반 논설문 작성 및 평가 시스템",
    page_icon="📰",
    layout="wide"
)

class NewsAPI:
    """뉴스 API 통합 클래스"""

    def __init__(self):
        self.naver_client_id = ""
        self.naver_client_secret = ""

    def search_naver_news(self, query: str, display: int = 10, start: int = 1) -> Dict:
        """네이버 뉴스 검색 API"""
        if not self.naver_client_id or not self.naver_client_secret:
            # API 키가 없는 경우 샘플 데이터 반환
            return self._get_sample_news_data(query)

        url = "https://openapi.naver.com/v1/search/news.json"
        headers = {
            "X-Naver-Client-Id": self.naver_client_id,
            "X-Naver-Client-Secret": self.naver_client_secret
        }
        params = {
            "query": query,
            "display": display,
            "start": start,
            "sort": "date"
        }

        try:
            response = requests.get(url, headers=headers, params=params)
            return response.json()
        except Exception as e:
            st.error(f"API 호출 오류: {e}")
            return self._get_sample_news_data(query)

    def _get_sample_news_data(self, query: str) -> Dict:
        """샘플 뉴스 데이터 생성"""
        sample_articles = [
            {
                "title": f"[뉴스] {query} 관련 주요 이슈 분석",
                "originallink": "https://example.com/news1",
                "link": "https://example.com/news1",
                "description": f"{query}에 대한 전문가들의 심층 분석이 담긴 기사입니다. 최근 동향과 향후 전망을 다루고 있습니다.",
                "pubDate": "Wed, 13 Aug 2025 09:00:00 +0900"
            },
            {
                "title": f"[사설] {query} 정책 방향성에 대한 제언",
                "originallink": "https://example.com/news2",
                "link": "https://example.com/news2",
                "description": f"{query} 정책의 현황과 문제점을 짚어보고, 개선 방안을 제시한 사설입니다.",
                "pubDate": "Wed, 13 Aug 2025 08:30:00 +0900"
            },
            {
                "title": f"[경제] {query}가 경제에 미치는 영향",
                "originallink": "https://example.com/news3",
                "link": "https://example.com/news3",
                "description": f"{query}가 국내 경제와 시장에 미치는 다양한 영향을 경제 전문가들이 분석했습니다.",
                "pubDate": "Wed, 13 Aug 2025 07:45:00 +0900"
            }
        ]

        return {
            "lastBuildDate": "Wed, 13 Aug 2025 10:00:00 +0900",
            "total": len(sample_articles),
            "start": 1,
            "display": len(sample_articles),
            "items": sample_articles
        }

class EditorialAnalyzer:
    """논설문 분석 및 평가 클래스"""

    def __init__(self):
        self.criteria = {
            "구조": ["서론-본론-결론 구성", "논리적 흐름", "단락 구성"],
            "내용": ["주장의 명확성", "근거의 타당성", "반박 고려"],
            "표현": ["어휘 선택", "문장 구성", "어조 일관성"],
            "설득력": ["논리적 일관성", "감정적 호소", "신뢰성"]
        }

    def analyze_structure(self, text: str) -> Dict:
        """논설문 구조 분석"""
        paragraphs = text.split('\n\n')
        word_count = len(text.split())
        sentence_count = len(re.findall(r'[.!?]+', text))

        return {
            "paragraph_count": len(paragraphs),
            "word_count": word_count,
            "sentence_count": sentence_count,
            "avg_words_per_sentence": round(word_count / max(sentence_count, 1), 1)
        }

    def evaluate_content(self, text: str) -> Dict:
        """내용 평가"""
        # 키워드 기반 간단 분석
        argument_keywords = ["따라서", "그러므로", "결론적으로", "주장", "생각", "견해"]
        evidence_keywords = ["연구", "조사", "데이터", "통계", "사실", "예시"]

        argument_score = sum(1 for keyword in argument_keywords if keyword in text)
        evidence_score = sum(1 for keyword in evidence_keywords if keyword in text)

        return {
            "argument_clarity": min(argument_score * 2, 10),
            "evidence_strength": min(evidence_score * 2.5, 10),
            "overall_content": (min(argument_score * 2, 10) + min(evidence_score * 2.5, 10)) / 2
        }

    def generate_feedback(self, analysis: Dict) -> List[str]:
        """개선 피드백 생성"""
        feedback = []

        if analysis["structure"]["paragraph_count"] < 3:
            feedback.append("📝 서론-본론-결론의 3단 구성을 명확히 해보세요.")

        if analysis["structure"]["avg_words_per_sentence"] > 30:
            feedback.append("✂️ 문장이 너무 길어요. 간결하고 명확한 문장으로 나누어보세요.")

        if analysis["content"]["argument_clarity"] < 5:
            feedback.append("🎯 주장을 더 명확하게 표현해보세요.")

        if analysis["content"]["evidence_strength"] < 5:
            feedback.append("📊 구체적인 근거나 사례를 더 추가해보세요.")

        return feedback

def main():
    st.title("📰 뉴스 기반 논설문 작성 및 평가 시스템")
    st.markdown("---")

    # 사이드바 메뉴
    menu = st.sidebar.selectbox(
        "메뉴 선택",
        ["🔍 뉴스 검색", "✍️ 논설문 작성", "📊 논설문 분석", "📈 데이터 시각화"]
    )

    # API 설정
    news_api = NewsAPI()
    analyzer = EditorialAnalyzer()

    if menu == "🔍 뉴스 검색":
        st.header("뉴스 검색 및 수집")

        # 검색 설정
        col1, col2 = st.columns([3, 1])
        with col1:
            search_query = st.text_input("검색어를 입력하세요:", value="인공지능")
        with col2:
            search_count = st.selectbox("검색 개수:", [5, 10, 20, 30], index=1)

        # API 키 설정 (선택사항)
        with st.expander("🔑 네이버 API 설정 (선택사항)"):
            col1, col2 = st.columns(2)
            with col1:
                client_id = st.text_input("Client ID:", type="password")
            with col2:
                client_secret = st.text_input("Client Secret:", type="password")

            if client_id and client_secret:
                news_api.naver_client_id = client_id
                news_api.naver_client_secret = client_secret
                st.success("API 키가 설정되었습니다!")

        if st.button("🔍 뉴스 검색", type="primary"):
            with st.spinner("뉴스를 검색하고 있습니다..."):
                news_data = news_api.search_naver_news(search_query, search_count)

                if 'items' in news_data and news_data['items']:
                    st.success(f"총 {len(news_data['items'])}개의 뉴스를 찾았습니다!")

                    # 검색 결과를 세션에 저장
                    st.session_state['news_results'] = news_data['items']
                    st.session_state['search_query'] = search_query

                    # 뉴스 목록 표시
                    for i, article in enumerate(news_data['items']):
                        with st.expander(f"📰 {i+1}. {article['title']}", expanded=i==0):
                            st.write(f"**발행일:** {article['pubDate']}")
                            st.write(f"**내용:** {article['description']}")
                            st.write(f"**링크:** [원문 보기]({article['originallink']})")

                            if st.button(f"이 기사로 논설문 작성", key=f"select_{i}"):
                                st.session_state['selected_article'] = article
                                st.success("기사가 선택되었습니다! '논설문 작성' 메뉴로 이동하세요.")
                else:
                    st.warning("검색 결과가 없습니다.")

    elif menu == "✍️ 논설문 작성":
        st.header("논설문 작성")

        # 선택된 기사 정보 표시
        if 'selected_article' in st.session_state:
            article = st.session_state['selected_article']
            st.info(f"선택된 기사: {article['title']}")
            with st.expander("선택된 기사 내용 보기"):
                st.write(article['description'])

        # 논설문 작성 도움말
        with st.expander("📝 논설문 작성 가이드"):
            st.markdown("""
            **좋은 논설문의 구조:**
            1. **서론**: 주제 제시 및 문제 제기
            2. **본론**: 주장과 근거 제시, 반박 고려
            3. **결론**: 주장 재확인 및 제언

            **작성 팁:**
            - 명확한 주장을 제시하세요
            - 구체적인 근거와 사례를 활용하세요
            - 반대 의견도 고려해보세요
            - 논리적 흐름을 유지하세요
            """)

        # 논설문 템플릿 선택
        template_option = st.selectbox(
            "템플릿 선택:",
            ["빈 문서", "기본 템플릿", "찬반 논증 템플릿", "문제 해결 템플릿"]
        )

        templates = {
            "빈 문서": "",
            "기본 템플릿": """[서론]
최근 [주제]에 대한 관심이 높아지고 있다.

[본론]
첫째,
둘째,
셋째,

[결론]
따라서 """,
            "찬반 논증 템플릿": """[서론]
[주제]에 대해 찬성과 반대 의견이 팽팽히 맞서고 있다.

[본론 - 찬성 근거]
찬성하는 이유는 다음과 같다.
첫째,
둘째,

[본론 - 반대 의견 검토]
물론 반대 의견도 있다.
하지만

[결론]
종합적으로 고려할 때, """,
            "문제 해결 템플릿": """[서론]
현재 [문제]가 심각한 사회적 이슈로 대두되고 있다.

[본론 - 문제 분석]
이 문제의 원인은 다음과 같다.

[본론 - 해결방안]
이를 해결하기 위한 방안을 제시하면,

[결론]
우리 사회가 이 문제를 해결하기 위해서는 """
        }

        # 논설문 작성 영역
        editorial_text = st.text_area(
            "논설문을 작성하세요:",
            value=templates[template_option],
            height=400,
            placeholder="여기에 논설문을 작성해주세요..."
        )

        col1, col2, col3 = st.columns([1, 1, 1])
        with col1:
            if st.button("💾 저장", type="primary"):
                st.session_state['editorial_text'] = editorial_text
                st.success("논설문이 저장되었습니다!")

        with col2:
            if st.button("🔄 초기화"):
                st.rerun()

        with col3:
            if st.button("📊 분석하기"):
                if editorial_text.strip():
                    st.session_state['editorial_text'] = editorial_text
                    st.success("분석 메뉴로 이동하여 결과를 확인하세요!")
                else:
                    st.warning("분석할 텍스트를 입력해주세요.")

    elif menu == "📊 논설문 분석":
        st.header("논설문 분석 및 평가")

        # 분석할 텍스트 확인
        if 'editorial_text' not in st.session_state or not st.session_state['editorial_text'].strip():
            st.warning("분석할 논설문이 없습니다. '논설문 작성' 메뉴에서 먼저 작성해주세요.")
            return

        editorial_text = st.session_state['editorial_text']

        # 텍스트 미리보기
        with st.expander("📝 작성된 논설문 보기"):
            st.write(editorial_text)

        # 분석 실행
        with st.spinner("논설문을 분석하고 있습니다..."):
            structure_analysis = analyzer.analyze_structure(editorial_text)
            content_analysis = analyzer.evaluate_content(editorial_text)

            # 종합 분석 결과
            overall_analysis = {
                "structure": structure_analysis,
                "content": content_analysis
            }

            feedback = analyzer.generate_feedback(overall_analysis)

        # 결과 표시
        st.subheader("📈 분석 결과")

        # 기본 통계
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("단락 수", structure_analysis["paragraph_count"])
        with col2:
            st.metric("단어 수", structure_analysis["word_count"])
        with col3:
            st.metric("문장 수", structure_analysis["sentence_count"])
        with col4:
            st.metric("평균 문장 길이", f"{structure_analysis['avg_words_per_sentence']}단어")

        # 내용 평가 점수
        st.subheader("📊 내용 평가")
        col1, col2 = st.columns(2)

        with col1:
            # 주장 명확성 게이지
            fig_arg = go.Figure(go.Indicator(
                mode = "gauge+number",
                value = content_analysis["argument_clarity"],
                domain = {'x': [0, 1], 'y': [0, 1]},
                title = {'text': "주장 명확성"},
                gauge = {'axis': {'range': [None, 10]},
                        'bar': {'color': "darkblue"},
                        'steps': [
                            {'range': [0, 5], 'color': "lightgray"},
                            {'range': [5, 8], 'color': "yellow"},
                            {'range': [8, 10], 'color': "green"}],
                        'threshold': {'line': {'color': "red", 'width': 4},
                                    'thickness': 0.75, 'value': 8}}))
            fig_arg.update_layout(height=300)
            st.plotly_chart(fig_arg, use_container_width=True)

        with col2:
            # 근거 강도 게이지
            fig_evi = go.Figure(go.Indicator(
                mode = "gauge+number",
                value = content_analysis["evidence_strength"],
                domain = {'x': [0, 1], 'y': [0, 1]},
                title = {'text': "근거 강도"},
                gauge = {'axis': {'range': [None, 10]},
                        'bar': {'color': "darkgreen"},
                        'steps': [
                            {'range': [0, 5], 'color': "lightgray"},
                            {'range': [5, 8], 'color': "yellow"},
                            {'range': [8, 10], 'color': "green"}],
                        'threshold': {'line': {'color': "red", 'width': 4},
                                    'thickness': 0.75, 'value': 8}}))
            fig_evi.update_layout(height=300)
            st.plotly_chart(fig_evi, use_container_width=True)

        # 개선 피드백
        st.subheader("💡 개선 제안")
        if feedback:
            for fb in feedback:
                st.write(f"• {fb}")
        else:
            st.success("🎉 훌륭한 논설문입니다! 특별한 개선점이 발견되지 않았습니다.")

        # 상세 분석 결과
        with st.expander("📋 상세 분석 결과"):
            st.json(overall_analysis)

    elif menu == "📈 데이터 시각화":
        st.header("뉴스 데이터 시각화")

        # 샘플 데이터 생성 (실제 환경에서는 수집된 데이터 사용)
        if 'news_results' in st.session_state:
            articles = st.session_state['news_results']
            query = st.session_state.get('search_query', '검색어')
        else:
            # 샘플 데이터
            articles = [
                {"title": "AI 기술 발전", "pubDate": "2025-08-13"},
                {"title": "AI 교육 도입", "pubDate": "2025-08-12"},
                {"title": "AI 윤리 문제", "pubDate": "2025-08-11"},
            ]
            query = "인공지능"

        st.subheader(f"'{query}' 관련 뉴스 분석")

        # 기간별 뉴스 발행 추이
        st.subheader("📅 기간별 뉴스 발행 추이")

        # 샘플 시계열 데이터 생성
        dates = pd.date_range(start='2025-08-01', end='2025-08-13', freq='D')
        counts = [5, 8, 12, 7, 15, 20, 18, 25, 22, 30, 28, 35, len(articles)]

        df_timeline = pd.DataFrame({
            'date': dates,
            'count': counts
        })

        fig_timeline = px.line(df_timeline, x='date', y='count',
                              title=f"'{query}' 관련 뉴스 발행량",
                              labels={'date': '날짜', 'count': '기사 수'})
        st.plotly_chart(fig_timeline, use_container_width=True)

        # 키워드 워드클라우드 (시뮬레이션)
        st.subheader("☁️ 키워드 클라우드")

        # 샘플 키워드 데이터
        sample_keywords = {
            '인공지능': 50, '기술': 40, '발전': 35, '교육': 30,
            '미래': 25, '혁신': 20, '산업': 18, '디지털': 15,
            '자동화': 12, '데이터': 10, '알고리즘': 8, '로봇': 6
        }

        # 워드클라우드 생성
        plt.figure(figsize=(10, 6))
        wordcloud = WordCloud(width=800, height=400,
                             background_color='white',
                             font_path=None,  # 한글 폰트 경로 (필요시 설정)
                             max_words=100).generate_from_frequencies(sample_keywords)

        plt.imshow(wordcloud, interpolation='bilinear')
        plt.axis('off')

        # Streamlit에 표시
        buf = BytesIO()
        plt.savefig(buf, format='png', bbox_inches='tight', dpi=300)
        buf.seek(0)
        st.image(buf, use_container_width=True)
        plt.close()

        # 카테고리별 분석
        st.subheader("📊 카테고리별 뉴스 분포")

        categories = ['정치', '경제', '사회', '기술', '국제']
        category_counts = [15, 25, 20, 30, 10]

        fig_pie = px.pie(values=category_counts, names=categories,
                        title="카테고리별 뉴스 분포")
        st.plotly_chart(fig_pie, use_container_width=True)

        # 감정 분석 (시뮬레이션)
        st.subheader("😊 뉴스 감정 분석")

        sentiment_data = {
            '긍정': 45,
            '중립': 35,
            '부정': 20
        }

        fig_sentiment = px.bar(x=list(sentiment_data.keys()),
                              y=list(sentiment_data.values()),
                              title="뉴스 감정 분포",
                              color=list(sentiment_data.keys()),
                              color_discrete_map={'긍정': 'green', '중립': 'gray', '부정': 'red'})
        st.plotly_chart(fig_sentiment, use_container_width=True)

    # 하단 정보
    st.markdown("---")
    st.markdown("""
    <div style='text-align: center'>
    <small>
    💡 <strong>사용 가능한 API:</strong><br>
    • 네이버 뉴스 검색 API<br>
    • BIG KINDS (한국언론진흥재단)<br>
    • 공공데이터포털 뉴스 API<br><br>

    📚 <strong>주요 기능:</strong><br>
    • 실시간 뉴스 검색 및 수집<br>
    • AI 기반 논설문 분석 및 평가<br>
    • 데이터 시각화 및 트렌드 분석<br>
    • 논설문 작성 가이드 및 템플릿 제공
    </small>
    </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()