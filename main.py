import os
import asyncio
import platform
import json
from dotenv import load_dotenv
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    ConversationHandler, MessageHandler, ContextTypes, filters
)

# --- Cargar token desde .env ---
load_dotenv()
TOKEN = os.getenv("TELEGRAM_TOKEN")

# Estados de la conversación
CANTIDAD, CATEGORIA, INGRESO = range(3)

# --- Diccionario global de la cuenta compartida ---
cuenta = {
    "saldo": 0,
    "gastos": []
}

# --- Funciones de persistencia ---
def guardar_datos():
    with open("data.json", "w") as f:
        json.dump(cuenta, f)

def cargar_datos():
    global cuenta
    try:
        with open("data.json", "r") as f:
            cuenta = json.load(f)
    except FileNotFoundError:
        cuenta = {"saldo": 0, "gastos": []}

# --- Función para mostrar menú ---
def mostrar_menu():
    keyboard = [
        [InlineKeyboardButton("Registrar gasto 📝", callback_data="gasto")],
        [InlineKeyboardButton("Añadir ingreso ➕", callback_data="ingreso")],
        [InlineKeyboardButton("Ver saldo 💰", callback_data="saldo")],
        [InlineKeyboardButton("Resumen mensual 📊", callback_data="resumen")],
        [InlineKeyboardButton("Configurar saldo inicial ⚙️", callback_data="inicio")],
        [InlineKeyboardButton("Resetear mes 🔄", callback_data="reset")]
    ]
    return InlineKeyboardMarkup(keyboard)

# --- Funciones del menú ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Selecciona una opción:", reply_markup=mostrar_menu())

# --- Flujo de registrar gasto ---
async def gasto_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("Ingresa la cantidad del gasto:")
    return CANTIDAD

async def recibir_cantidad(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["cantidad"] = update.message.text
    await update.message.reply_text("Ahora ingresa la categoría del gasto:")
    return CATEGORIA

async def recibir_categoria(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cantidad = int(context.user_data["cantidad"])
    categoria = update.message.text

    cuenta["saldo"] -= cantidad
    cuenta["gastos"].append({"cantidad": cantidad, "categoria": categoria})
    guardar_datos()

    await update.message.reply_text(
        f"Gasto registrado: {cantidad} en {categoria} ✅\nSaldo restante: {cuenta['saldo']} 💰",
        reply_markup=mostrar_menu()
    )
    return ConversationHandler.END

# --- Flujo de añadir ingreso ---
async def ingreso_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("Ingresa el monto que deseas añadir al capital:")
    return INGRESO

async def recibir_ingreso(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cantidad = int(update.message.text)
    cuenta["saldo"] += cantidad
    guardar_datos()

    await update.message.reply_text(
        f"✅ Se añadió {cantidad} al capital.\nSaldo actual: {cuenta['saldo']} 💰",
        reply_markup=mostrar_menu()
    )
    return ConversationHandler.END

# --- Resetear mes ---
async def reset_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    cuenta["saldo"] = 0
    cuenta["gastos"] = []
    guardar_datos()

    await query.edit_message_text(
        "✅ Se ha reiniciado el mes. La lista de gastos y el saldo fueron borrados.",
        reply_markup=mostrar_menu()
    )

# --- Otros botones ---
async def saldo_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        f"Saldo actual: {cuenta['saldo']} 💰",
        reply_markup=mostrar_menu()
    )

async def resumen_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if cuenta["gastos"]:
        resumen = "📊 Resumen mensual:\n"
        for g in cuenta["gastos"]:
            resumen += f"- {g['cantidad']} en {g['categoria']}\n"
        resumen += f"\nSaldo restante: {cuenta['saldo']} 💰"
        await query.edit_message_text(resumen, reply_markup=mostrar_menu())
    else:
        await query.edit_message_text(
            "No tienes gastos registrados aún 📝",
            reply_markup=mostrar_menu()
        )

async def inicio_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "Usa /inicio <cantidad> para configurar tu saldo inicial ⚙️",
        reply_markup=mostrar_menu()
    )

async def inicio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cantidad = int(context.args[0])
    cuenta["saldo"] = cantidad
    guardar_datos()

    await update.message.reply_text(
        f"Saldo inicial configurado en {cantidad} 💰",
        reply_markup=mostrar_menu()
    )

# --- Configuración principal ---
def main():
    if not TOKEN:
        raise RuntimeError("Falta TELEGRAM_TOKEN en .env")

    # 👇 Solo aplica en Windows
    if platform.system() == "Windows":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    cargar_datos()  # Restaurar datos al iniciar

    app = ApplicationBuilder().token(TOKEN).build()

    # Conversación para registrar gasto
    gasto_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(gasto_button, pattern="^gasto$")],
        states={
            CANTIDAD: [MessageHandler(filters.TEXT & ~filters.COMMAND, recibir_cantidad)],
            CATEGORIA: [MessageHandler(filters.TEXT & ~filters.COMMAND, recibir_categoria)],
        },
        fallbacks=[],
        per_chat=True
    )

    # Conversación para añadir ingreso
    ingreso_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(ingreso_button, pattern="^ingreso$")],
        states={
            INGRESO: [MessageHandler(filters.TEXT & ~filters.COMMAND, recibir_ingreso)],
        },
        fallbacks=[],
        per_chat=True
    )

    # Handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("inicio", inicio))
    app.add_handler(gasto_conv)
    app.add_handler(ingreso_conv)
    app.add_handler(CallbackQueryHandler(saldo_button, pattern="^saldo$"))
    app.add_handler(CallbackQueryHandler(resumen_button, pattern="^resumen$"))
    app.add_handler(CallbackQueryHandler(inicio_button, pattern="^inicio$"))
    app.add_handler(CallbackQueryHandler(reset_button, pattern="^reset$"))

    # Ejecutar bot
    app.run_polling()

if __name__ == "__main__":
    main()
