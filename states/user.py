from aiogram.fsm.state import State, StatesGroup


class AdminStates(StatesGroup):
    edit_user_balance = State()
    edit_model_name = State()
    edit_model_price = State()
