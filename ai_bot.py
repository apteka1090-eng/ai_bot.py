import telebot
from telebot import types
from groq import Groq

# 1. АСОСИЙ СОЗЛАМАЛАР
BOT_TOKEN = "8927163786:AAFdNQEhUsio8OlvrU1mszuHvuz-4Z4GLTo"
GROQ_API_KEY = "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"

bot = telebot.TeleBot(BOT_TOKEN)
groq_client = Groq(api_key=GROQ_API_KEY)

# Фойдаланувчи маълумотлари омбори
user_modes = {}        # Қайси режимдалиги ('info', 'doctor', 'combo')
user_contexts = {}     # Суҳбат тарихи (контекст)
user_last_drug = {}    # Охирги қидирилган дори номи (инлайн тугмалар учун)

# 2. РЕЖИМЛАР УЧУН AI ЙЎРИҚНОМАЛАРИ (SYSTEM PROMPTS)
PROMPT_INFO_MODE = (
    "Sen faqat dorilar bo'yicha ma'lumot beruvchi mutaxassis botisan. Bemor bilan muloqot qilmaysan. "
    "Foydalanuvchi dori nomini yozsa, u dori nima uchun ishlatilishi, dozasi va nojo'ya ta'sirlarini aniq yoz. "
    "Faqat o'zbek tilida, LOTIN alifbosida, chiroyli va tartibli yozib ber. Oxirida shifokor bilan maslahatlashishni eslat."
)

PROMPT_DOCTOR_MODE = (
    "Sen professional va xushmuomala shifokorsan. Foydalanuvchi o'z kasallik belgilarini yozsa, u bilan shifokor-bemor suhbatini qur. "
    "MULOQOT QOIDALARI:\n"
    "1. Bemorga aniq dori tavsiya qilma, faqat umumiy tibbiy maslahat va tavsiyalar ber (Masalan: ko'proq suyuqlik ichish, dam olish).\n"
    "2. Skrining qil: Bemorga qo'shimcha simptomlar haqida savol ber (Masalan: isitma bormi, qon bosimi qanday?).\n"
    "3. Parhez va hayot tarzi bo'yicha maslahatlar qo'sh.\n"
    "4. Yosh va homiladorlik holatini aniqlashtir.\n"
    "5. TEZ YORDAM: Agar bemor o'tkir yurak og'rig'i, nafas qisishi kabi xavfli belgilarni yozsa, muloqotni to'xtat va katta harflar bilan 'TEZDA 103 GA QO'NG'IROQ QILING!' deb ogohlantir.\n"
    "Faqat o'zbek tilida, LOTIN alifbosida yoz."
)

PROMPT_COMBO_MODE = (
    "Sen ham shifokor, ham dori mutaxassisibsan (Kombinatsiyalashgan rejim). Bemor o'z dardini aytsa, sen unga ham shifokorlik qilasan, ham aniq dori tavsiya qilasan.\n"
    "MULOQOT QOIDALARI:\n"
    "1. Bemorning dardini eshit va skrining qil (qo'shimcha savollar ber: yoshi, homiladorligi va h.k.).\n"
    "2. Unga aniq dori tavsiya qil (Masalan: isitma chiqayotgan bo'lsa, Ibuklin tabletkasini 2 mahal ichishni va qanday qabul qilishni tushuntir).\n"
    "3. Tavsiya qilgan doring haqida qisqacha ma'lumot berib o't (nima uchun aynan shu dori va uning ta'siri).\n"
    "4. Parhez va foydali maslahatlarni qo'sh.\n"
    "5. TEZ YORDAM: Simptomlar hayot uchun xavfli bo'lsa (o'tkir og'riqlar), darhol 'TEZDA 103 GA QO'NG'IROQ QILING!' deb yoz.\n"
    "Faqat o'zbek tilida, LOTIN alifbosida chiroyli qilib yoz."
)

# 3. КЛАВИАТУРАЛАР (МЕНЮЛАР)
def get_start_keyboard():
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
    btn1 = types.KeyboardButton("💊 Dori haqida ma'lumot olish")
    btn2 = types.KeyboardButton("🩺 AI Shifokor konsultatsiyasi")
    btn3 = types.KeyboardButton("🔄 Shifokor tavsiyasi + Dori ma'lumoti (Universal)")
    keyboard.add(btn1, btn2, btn3)
    return keyboard

def get_back_keyboard():
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    btn_back = types.KeyboardButton("⬅️ Bosh menuga qaytish")
    keyboard.add(btn_back)
    return keyboard

def get_drug_keyboard():
    keyboard = types.InlineKeyboardMarkup(row_width=1)
    btn_info = types.InlineKeyboardButton("💊 Qo'llanilishi (Info)", callback_data="drug_info")
    btn_dose = types.InlineKeyboardButton("⏳ Dozirovka va Ichilishi", callback_data="drug_dose")
    btn_side = types.InlineKeyboardButton("❌ Nojo'ya ta'sirlari", callback_data="drug_side")
    keyboard.add(btn_info, btn_dose, btn_side)
    return keyboard


# 4. БОТ БУЙРУҚЛАРИ
@bot.message_handler(commands=['start', 'reset'])
def send_welcome(message):
    user_id = message.chat.id
    user_modes[user_id] = None
    user_contexts[user_id] = []
    user_last_drug[user_id] = None
    
    bot.send_message(
        user_id,
        "Assalomu alaykum! Tibbiy yordamchi botga xush kelibsiz. 🩺\n\n"
        "Sizga qanday yordam kerak? Iltimos, quyidagi rejimlardan birini tanlang:",
        reply_markup=get_start_keyboard()
    )


# 5. РЕЖИМЛАРНИ БОШҚАРИШ ВА АЛМАШТИРИШ
@bot.message_handler(func=lambda message: message.text in [
    "💊 Dori haqida ma'lumot olish", 
    "🩺 AI Shifokor konsultatsiyasi", 
    "🔄 Shifokor tavsiyasi + Dori ma'lumoti (Universal)",
    "⬅️ Bosh menuga qaytish"
])
def handle_modes(message):
    user_id = message.chat.id
    text = message.text

    if text == "⬅️ Bosh menuga qaytish":
        user_modes[user_id] = None
        user_contexts[user_id] = []
        user_last_drug[user_id] = None
        bot.send_message(user_id, "Bosh menuga qaytdingiz. Rejimni qayta tanlang:", reply_markup=get_start_keyboard())
        return

    if text == "💊 Dori haqida ma'lumot olish":
        user_modes[user_id] = 'info'
        user_contexts[user_id] = [{"role": "system", "content": PROMPT_INFO_MODE}]
        bot.send_message(user_id, "Siz **Dori ma'lumotnomasi** rejimidasiz. Menga dori nomini yozing:", reply_markup=get_back_keyboard())

    elif text == "🩺 AI Shifokor konsultatsiyasi":
        user_modes[user_id] = 'doctor'
        user_contexts[user_id] = [{"role": "system", "content": PROMPT_DOCTOR_MODE}]
        bot.send_message(user_id, "Siz **AI Shifokor** rejimidasiz. O'zingizdagi kasallik belgilarini yozib qoldiring:", reply_markup=get_back_keyboard())

    elif text == "🔄 Shifokor tavsiyasi + Dori ma'lumoti (Universal)":
        user_modes[user_id] = 'combo'
        user_contexts[user_id] = [{"role": "system", "content": PROMPT_COMBO_MODE}]
        bot.send_message(user_id, "Siz **Universal** rejimdasiz. Kasallik alomatlarini yozing, men sizni eshitib, dori tavsiya qilaman va u haqida ma'lumot beraman:", reply_markup=get_back_keyboard())


# 6. АСОСИЙ МАТНЛИ СЎРОВЛАР (ГРОҚ БИЛАН СУҲБАТ)
@bot.message_handler(func=lambda message: True)
def handle_ai_chat(message):
    user_id = message.chat.id
    text = message.text.strip()
    
    if user_modes.get(user_id) is None:
        bot.send_message(user_id, "Iltimos, avval pastdagi tugmalardan birini bosib, ish rejimini tanlang! 👇", reply_markup=get_start_keyboard())
        return

    bot.send_chat_action(user_id, 'typing')
    user_contexts[user_id].append({"role": "user", "content": text})

    if len(user_contexts[user_id]) > 13:
        user_contexts[user_id] = [user_contexts[user_id][0]] + user_contexts[user_id][-12:]

    try:
        chat_completion = groq_client.chat.completions.create(
            messages=user_contexts[user_id],
            model="llama-3.3-70b-versatile",
            temperature=0.4  
        )
        
        bot_reply = chat_completion.choices[0].message.content
        user_contexts[user_id].append({"role": "assistant", "content": bot_reply})
        
        if len(text.split()) <= 2 or user_modes[user_id] == 'info':
            user_last_drug[user_id] = text  
            bot.send_message(
                user_id, 
                bot_reply + f"\n\n{text} bo'yicha qo'shimcha ma'lumot olishingiz mumkin:", 
                reply_markup=get_drug_keyboard()
            )
        else:
            bot.send_message(user_id, bot_reply, reply_markup=get_back_keyboard())
            
    except Exception as e:
        print(f"Xatolik yuz berdi: {e}")
        bot.send_message(user_id, "Tizimda biroz yuklama bor. Iltimos, birozdan so'ng qayta urinib ko'ring.", reply_markup=get_back_keyboard())


# 7. ИНЛАЙН ТУГМАЛАР БОСИЛГАНДА ИШЛАЙДИГАН ҚИСМ
@bot.callback_query_handler(func=lambda call: call.data.startswith('drug_'))
def handle_drug_buttons(call):
    user_id = call.message.chat.id
    action = call.data
    
    drug_name = user_last_drug.get(user_id)
    if not drug_name:
        for msg in reversed(user_contexts.get(user_id, [])):
            if msg["role"] == "user":
                drug_name = msg["content"]
                break
    if not drug_name:
        drug_name = "bu dori"
    
    if action == "drug_info":
        prompt = f"'{drug_name}' dorisi nima uchun ishlatiladi? Qisqa va tushunarli qilib lotin alifbosida tushuntir."
    elif action == "drug_dose":
        prompt = f"'{drug_name}' dorisining dozirovkasi qanday? Kattalar va bolalar uchun qachon va qancha ichiladi? Lotin alifbosida yoz."
    elif action == "drug_side":
        prompt = f"'{drug_name}' dorisining qanday nojo'ya ta'sirlari va qarshi ko'rsatmalari bor? Kimlarga mumkin emas? Lotin alifbosida yoz."

    bot.send_chat_action(user_id, 'typing')
    bot.answer_callback_query(call.id, "Ma'lumot tayyorlanmoqda...")

    user_contexts[user_id].append({"role": "user", "content": prompt})
    
    try:
        chat_completion = groq_client.chat.completions.create(
            messages=user_contexts[user_id],
            model="llama-3.3-70b-versatile",
            temperature=0.4
        )
        bot_reply = chat_completion.choices[0].message.content
        user_contexts[user_id].append({"role": "assistant", "content": bot_reply})
        
        bot.send_message(user_id, bot_reply, reply_markup=get_drug_keyboard())
    except Exception as e:
        print(f"Xatolik: {e}")
        bot.send_message(user_id, "Tizimda uzilish bo'ldi. Qaytadan urinib ko'ring.")


# БОТНИ СТАРТ ҚИЛИШ
print("ХАБАРНОМА: БОТ ХАТОСИЗ ИШГА ТУШДИ...")
bot.infinity_polling()