import discord
from discord.ext import commands
from openai import OpenAI
import os
from dotenv import load_dotenv
from subprocess import check_output
import mysql.connector
import re
from googleapiclient.discovery import build


load_dotenv()  # .env 파일에서 환경변수 로드

# MySQL 연결 설정 (환경변수 대신 코드 내에 직접 입력)
db_config = {
    'host': 'localhost',  # 데이터베이스 호스트
    'user': 'root',  # MySQL 사용자명
    'password': '1234',  # MySQL 비밀번호
    'database': 'discord_bot'  # 데이터베이스 이름
}

api_key = os.getenv("OPENAI_API_KEY")
bot_token = os.getenv("DISCORD_BOT_TOKEN")
google_cse_id = os.getenv("GOOGLE_CSE_ID")
google_api_key = os.getenv("GOOGLE_API_KEY")
search_service = build("customsearch", "v1", developerKey=google_api_key)

client = OpenAI()

command_active = False

# 디스코드 봇 설정
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

# !견적 명령어: 견적 정보 출력
@bot.command(name="견적")
async def fetch_estimates(ctx):
    global command_active
    if command_active:
        await ctx.send("다른 명령어가 실행중")
        return
    
    command_active = True
    conn = None  # conn 변수를 처음에 None으로 초기화
    try:
        # MySQL 연결
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor(dictionary=True)

        

        # computer_estimates 테이블에서 데이터 조회
        cursor.execute("SELECT id, estimate_name, description, total_price FROM computer_estimates")
        estimates = cursor.fetchall()

        if not estimates:
            await ctx.send("등록된 견적이 없습니다.")
        else:
            # 결과 메시지 생성
            result_message = "**📋 견적 목록:**\n"
            for estimate in estimates:
                result_message += (
                    f"**{estimate['id']}번\n"
                    f"**이름:** {estimate['estimate_name']}\n"
                    f"**설명:** {estimate['description']}\n"
                    f"**총합: 약** {int(estimate['total_price'])}원\n\n"
                )
            result_message += f"자세한 부품 구성을 보고싶거나 가격을 조정하고 싶다면 !1 이런식으로 명령어를 작성해주세요" 
            await ctx.send(result_message)
    except Exception as e:
        await ctx.send(f"에러 발생: {e}")
    finally:
        # conn이 연결되어 있는지 확인하고 닫기
        if conn and conn.is_connected():
            cursor.close()
            conn.close()
        command_active = False

#견적 부품 보여주기
@bot.command(name="1", aliases=["2", "3", "4", "5", "6"])
async def fetch_estimate_details(ctx):
    global command_active
    if command_active:
        await ctx.send("다른 명령어가 실행중입니다.")
        return

    command_active = True
    conn = None
    try:
        estimate_id = int(ctx.invoked_with)  # 명령어에서 번호를 가져옴
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor(dictionary=True)

        # 특정 견적의 부품 정보 가져오기
        cursor.execute("""
            SELECT ed.product_name, ed.category, ed.price, ed.quantity, p.product_url
            FROM estimate_details ed
            JOIN products p ON ed.product_id = p.product_id
            WHERE ed.estimate_id = %s
        """, (estimate_id,))
        details = cursor.fetchall()

        if not details:
            await ctx.send(f"{estimate_id}번 견적의 세부 정보가 없습니다.")
        else:
            # 세부 정보 메시지 생성
            result_message = f"**{estimate_id}번 견적의 상세 정보:**\n"
            for detail in details:
                result_message += (
                    f"- **부품 이름:** [{detail['product_name']}]({detail['product_url']})\n"
                    f"  **카테고리:** {detail['category']}\n"
                    f"  **가격:** {int(detail['price']):,}원\n"
                    f"  **수량:** {detail['quantity']}개\n\n"
                )
            await ctx.send(result_message)
    except Exception as e:
        await ctx.send(f"에러 발생: {e}")
    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()
        command_active = False

async def fetch_price_from_message(message):
    # 메시지에서 "가격" 키워드와 제품 이름 추출
    match = re.search(r'([a-zA-Z0-9가-힣\s]+)\s*가격', message.content, re.IGNORECASE)
    if not match:
        return None, "❌ 검색 키워드를 찾을 수 없습니다. '제품명 가격' 형식으로 입력해주세요."

    product_keyword = match.group(1).strip().replace(" ", "")  # 키워드 추출 및 공백 제거

    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor(dictionary=True)

        # SQL 쿼리 작성
        query = """
            SELECT product_name, price, product_url 
            FROM products 
            WHERE REPLACE(product_name, ' ', '') LIKE %s
        """
        cursor.execute(query, (f"%{product_keyword}%",))
        results = cursor.fetchall()  # 모든 결과 읽기

        if not results:
            return product_keyword, f"🔍 '{product_keyword}'에 대한 검색 결과가 없습니다."

        # 검색 결과를 메시지로 생성
        response_message = f"🔍 '{product_keyword}' 검색 결과:\n\n"
        for result in results:
            response_message += (
                f"** 제품 이름:** [{result['product_name']}]({result['product_url']})\n"
                f"　💰 **가격:** `{int(result['price']):,}원`\n\n"
            )
        return product_keyword, response_message.strip()  # 키워드와 메시지 반환

    except mysql.connector.Error as e:
        print(f"❌ Database Error: {e}")
        return None, "⚠️ 데이터베이스 연결 중 문제가 발생했습니다. 다시 시도해주세요."

    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()

@bot.command(name="검색")
async def google_search(ctx, *, query: str):
    global command_active
    if command_active:
        await ctx.send("다른 명령어가 실행 중입니다.")
        return

    command_active = True

    try:
        # 자연어 분석: 견적 관련 요청인지 확인
        gpt_analysis = client.chat.completions.create(
            model="gpt-4-turbo",
            messages=[
                {"role": "system", "content": "너는 사용자가 요청한 문장을 분석하는 AI야. 이 문장이 컴퓨터 부품 견적 요청인지 일반적인 정보 검색 요청인지 판단해줘."},
                {"role": "user", "content": f"'{query}'라는 요청이 견적 요청인가, 아니면 일반적인 검색 요청인가? 만약 견적 요청이라면 요청된 목적을 간략히 설명해줘."}
            ]
        )
        analysis_response = gpt_analysis.choices[0].message.content

        # GPT 분석 결과 확인
        if "견적" in analysis_response or "추천" in analysis_response or "예산" in analysis_response:
            # 견적 요청으로 간주
            await ctx.send("검색중입니다 잠시만 기다려주세요.......")

            # Google Custom Search API를 통해 검색
            res = search_service.cse().list(
                q=query,
                cx=google_cse_id,
                num=5
            ).execute()

            if 'items' in res:
                # 검색 결과를 정리
                search_results = ""
                for idx, item in enumerate(res['items'], 1):
                    search_results += (
                        f"{idx}. **{item['title']}**\n"
                        f"URL: {item['link']}\n"
                        f"설명: {item['snippet']}\n\n"
                    )

                # GPT에게 검색 결과를 전달하고 추천 견적 요청
                async with ctx.typing():
                    gpt_response = client.chat.completions.create(
                        model="gpt-4-turbo",
                        messages=[
                            {"role": "system", "content": "너는 컴퓨터 전문가야. 사용자가 입력한 요청과 검색 결과를 바탕으로 예산 내 최적의 추천 견적을 만들어줘. 최신부품들 위주로 견적을 만들어줘"},
                            {"role": "user", "content": f"다음은 '{query}'에 대한 검색 결과입니다:\n\n{search_results}"},
                            {"role": "user", "content": f"이 정보를 기반으로 '{query}'에 맞는 최적의 추천 견적을 만들어줘."},
                        ]
                    )
                    answer = gpt_response.choices[0].message.content

                await ctx.send(f"**'{query}'에 대한 추천 견적:**\n\n{answer}")

            else:
                await ctx.send("검색 결과를 찾을 수 없습니다.")
        else:
            # 일반 검색 요청으로 간주
            res = search_service.cse().list(
                q=query,
                cx=google_cse_id,
                num=5  # 검색 결과 제한
            ).execute()

            if 'items' in res:
                # 검색 결과를 정리
                search_results = "\n".join(
                    f"{idx}. **{item['title']}**\nURL: {item['link']}\n설명: {item['snippet']}\n"
                    for idx, item in enumerate(res['items'], start=1)
                )
                await ctx.send(f"**🔍 검색 결과:**\n\n{search_results}")
            else:
                await ctx.send("검색 결과를 찾을 수 없습니다.")

    except Exception as e:
        await ctx.send(f"에러 발생: {e}")
    finally:
        command_active = False


# 봇이 준비되었을 때 실행되는 이벤트
@bot.event
async def on_ready():
    print(f'We have logged in as {bot.user}')

@bot.event
async def on_message(message):
    global command_active

    # 봇 메시지는 무시
    if message.author == bot.user:
        return

    # 명령어를 처리하는 경우
    if message.content.startswith("!"):
        if command_active:  # 다른 명령어 실행 중일 경우 무시
            return
        await bot.process_commands(message)
        return

    # 가격 관련 메시지를 처리
    if "가격" in message.content:
        product_keyword, response_message = await fetch_price_from_message(message)
        if response_message:
            await message.channel.send(f"'{product_keyword}' 검색 결과:\n{response_message}")
        else:
            await message.channel.send(f"'{product_keyword}'에 대한 정보를 찾을 수 없습니다.")
        return

    # 일반 메시지는 GPT에게 전달
    try:
        async with message.channel.typing():
            response = client.chat.completions.create(
                model="gpt-4-turbo",
                messages=[
                    {"role": "system", "content": "너의 이름은 ComputerHelper이고 유용한 컴퓨터 견적을 내주는 인공지능챗봇이야. 항상 존댓말로 대답하고 컴퓨터를 사고싶다고 하면 !견적 명령어를 사용하도록 유도해 !견적 명령어에는 아무말 하지마"},
                    {"role": "user", "content": message.content},
                ]
            )

        answer = response.choices[0].message.content
        await message.channel.send(answer)
    except Exception as e:
        await message.channel.send(f"에러 발생: {e}")


bot.run(bot_token)
