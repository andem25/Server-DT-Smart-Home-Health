from telegram import Update
from telegram.ext import ContextTypes, Updater, CommandHandler

async def calc_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handler for the /calc command that performs basic calculations.

    Usage: /calc 2 + 2
    """
    try:
        # Join all arguments after the command
        expression = " ".join(context.args)

        if not expression:
            await update.message.reply_text(
                "Please provide an expression to calculate. \nExample: /calc 2 * 2"
            )
            return

        # Evaluate the expression safely
        allowed = "0123456789+-*/() "
        if not all(c in allowed for c in expression):
            await update.message.reply_text(
                "Invalid characters in expression. Only numbers and "
                "basic operators (+, -, *, /, ) are allowed."
            )
            return

        # Calculate the result
        result = eval(expression)  # CAUTION: eval can be unsafe in real-world scenarios

        await update.message.reply_text(f"Expression: {expression} = {result}")

    except (SyntaxError, ZeroDivisionError, NameError) as e:
        await update.message.reply_text(
            "Error in calculation: {str(e)}. Please check your expression."
        )
