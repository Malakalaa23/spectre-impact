# payment_processor.py – Payment processing module
def process_payment(amount, user):
    if not user:
        raise ValueError("User cannot be None")
    # BUG: This returns the new balance but doesn't update the user's balance!
    return user.balance - amount

def calculate_discount(amount, percentage):
    # BUG: No validation that percentage is between 0 and 100!
    return amount * (percentage / 100)
