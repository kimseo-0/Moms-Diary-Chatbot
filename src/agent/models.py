from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from dotenv import load_dotenv
load_dotenv()

# 라우팅 및 제어용 (빠르고 저렴한 모델)
llm_ctrl = ChatOpenAI(model="gpt-4.1-mini", temperature=0) 
# 답변 생성 및 RAG용 (고성능 모델)
llm_agent = ChatOpenAI(model="gpt-4o", temperature=0)