"""
financial.py - Financial calculation utiltiy functions.

Copyright (c) 2019 by Thomas J. Daley. All Rights Reserved.
"""
from collections import namedtuple
from datetime import datetime
from datetime import date
import numpy as np
import pandas as pd
from dateutil.relativedelta import relativedelta
from decimal import Decimal, ROUND_DOWN
ROUNDING = ROUND_DOWN  # Default rounding method


class FinancialCalculators(object):
    """
    Encapsulates the features of various financial calculators.
    """
    def __init__(self):
        """
        Instance initializer.
        """
        pass

    @staticmethod
    def payment(payment_count, annual_rate, principal_value, use_numpy=False)->Decimal:
        """
        Calculate a payment for an amortized loan.

        Args:
            payment_count (int): Number of payments. E.g. a 30 year loan with monthly
                payments has 360 payments.
            annual_rate (Decimal): Annual rate of interest.
            principal_value (float): Amount borrowed.
            use_numpy (bool): Whether to use the numpy pmt function?
                The timing difference on my system on 9/12/2019 on 100,000 iterations is:
                    use_numpy = TRUE : 3.0392037999999997
                    use_numpy = FALSE: 0.9322978000000002
        """
        if use_numpy:
            payment = Decimal(np.pmt(annual_rate / 12, payment_count, principal_value)) \
                .quantize(Decimal('.01'), rounding=ROUND_DOWN)
        else:
            monthly_rate = Decimal(annual_rate / 12).quantize(Decimal('.0001'))
            pc = Decimal(payment_count).quantize(Decimal('.0001'))
            pv = Decimal(principal_value).quantize(Decimal('.0001'))

            discount_rate = Decimal(
                ((((1 + monthly_rate)**pc) - 1) / (monthly_rate * (1 + monthly_rate)**pc))
            )

            payment = Decimal(pv / discount_rate).quantize(Decimal('.01'), rounding=ROUND_DOWN)

        return payment

    @staticmethod
    def amortization_list(payment_count, annual_rate, principal_value, first_payment, rounding=ROUNDING)->list:
        """
        Calculate a loan amortization schedule.

        Args:
            payment_count (int): Number of payments. E.g. a 30 year loan with monthly
                payments has 360 payments.
            annual_rate (Decimal): Annual rate of interest.
            principal_value (float): Amount borrowed.
            first_payment (str): Date first payment is due YYYY-MM-DD

        Returns:
            (list): List of tuples each having the following properties:
                .date - Payment date
                .beginning_principal - Loan balance before payment is made
                .interest - Interest accrued since previous payment date
                .payment - Amount of payment due
                .ending_principal - Loan balance after payment is made
        """
        precision = '.0001'
        result = []
        fields = ['date', 'beginning_principal', 'interest', 'payment', 'ending_principal']
        Payment = namedtuple('Payment', fields)
        payment = FinancialCalculators.payment(payment_count, annual_rate, principal_value)
        annual_rate = Decimal(annual_rate).quantize(Decimal(precision))
        monthly_rate = Decimal(annual_rate / 12).quantize(Decimal(precision))

        payment_date = datetime.strptime(first_payment, '%Y-%m-%d')
        beginning_principal = Decimal(principal_value).quantize(Decimal(precision))

        for payment_number in range(payment_count):
            interest = Decimal(beginning_principal * monthly_rate) \
                .quantize(Decimal(precision), rounding=rounding)
            ending_principal = Decimal(beginning_principal + interest - payment) \
                .quantize(Decimal(precision), rounding=rounding)

            # Adjustment for last payment
            if ending_principal < 0:
                payment -= ending_principal
                ending_principal = 0.0
            entry = Payment(payment_date, beginning_principal, interest, payment, ending_principal)
            result.append(entry)
            beginning_principal = ending_principal
            payment_date = payment_date + relativedelta(months=+1)

        return result

    @staticmethod
    def amortization_df(interest_rate, years, payments_year, principal, addl_principal=0, start_date=date.today()):
        """
        Calculate the amortization schedule given the loan details.

        FROM: https://pbpython.com/amortization-model.html

        Args:
            interest_rate: The annual interest rate for this loan
            years: Number of years for the loan
            payments_year: Number of payments in a year
            principal: Amount borrowed
            addl_principal (optional): Additional payments to be made each period. Assume 0 if nothing provided.
            start_date (optional): Start date. Will start on first of next month if none provided

        Returns:
            schedule: Amortization schedule as a pandas dataframe
            summary: Pandas dataframe that summarizes the payoff information
        """
        # Ensure the additional payments are negative
        if addl_principal > 0:
            addl_principal = -addl_principal

        # Create an index of the payment dates
        rng = pd.date_range(start_date, periods=years * payments_year, freq='MS')
        rng.name = "Payment_Date"

        # Build up the Amortization schedule as a DataFrame
        df = pd.DataFrame(index=rng, columns=['Payment', 'Principal', 'Interest',
                                              'Addl_Principal', 'Curr_Balance'], dtype='float')

        # Add index by period (start at 1 not 0)
        df.reset_index(inplace=True)
        df.index += 1
        df.index.name = "Period"

        # Calculate the payment, principal and interests amounts using built in Numpy functions
        per_payment = np.pmt(interest_rate / payments_year, years * payments_year, principal)
        df["Payment"] = per_payment
        df["Principal"] = np.ppmt(interest_rate / payments_year, df.index, years * payments_year, principal)
        df["Interest"] = np.ipmt(interest_rate / payments_year, df.index, years * payments_year, principal)

        # Round the values
        df = df.round(2)

        # Add in the additional principal payments
        df["Addl_Principal"] = addl_principal

        # Store the Cumulative Principal Payments and ensure it never gets larger than the original principal
        df["Cumulative_Principal"] = (df["Principal"] + df["Addl_Principal"]).cumsum()
        df["Cumulative_Principal"] = df["Cumulative_Principal"].clip(lower=-principal)

        # Calculate the current balance for each period
        df["Curr_Balance"] = principal + df["Cumulative_Principal"]

        # Determine the last payment date
        try:
            last_payment = df.query("Curr_Balance <= 0")["Curr_Balance"].idxmax(axis=1, skipna=True)
        except ValueError:
            last_payment = df.last_valid_index()

        last_payment_date = "{:%m-%d-%Y}".format(df.loc[last_payment, "Payment_Date"])

        # Truncate the data frame if we have additional principal payments:
        if addl_principal != 0:

            # Remove the extra payment periods
            df = df.ix[0:last_payment].copy()

            # Calculate the principal for the last row
            df.ix[last_payment, "Principal"] = -(df.ix[last_payment - 1, "Curr_Balance"])

            # Calculate the total payment for the last row
            df.ix[last_payment, "Payment"] = df.ix[last_payment, ["Principal", "Interest"]].sum()

            # Zero out the additional principal
            df.ix[last_payment, "Addl_Principal"] = 0

        # Get the payment info into a DataFrame in column order
        payment_info = (df[["Payment", "Principal", "Addl_Principal", "Interest"]]
                        .sum().to_frame().T)

        # Format the Date DataFrame
        # TODO: Change to from_dict()
        payment_details = pd.DataFrame.from_items(
            [('payoff_date', [last_payment_date]),
             ('Interest Rate', [interest_rate]),
             ('Number of years', [years])])
        # Add a column showing how much we pay each period.
        # Combine addl principal with principal for total payment
        payment_details["Period_Payment"] = round(per_payment, 2) + addl_principal

        payment_summary = pd.concat([payment_details, payment_info], axis=1)
        return df, payment_summary


def numpy_test():
    calculator = FinancialCalculators()
    pmt = calculator.payment(360, .06, 100000, True)


def no_numpy_test():
    calculator = FinancialCalculators()
    pmt = calculator.payment(360, .06, 100000, False)

if __name__ == "__main__":
    calculator = FinancialCalculators()
    print("Payment:", calculator.payment(360, .06, 100000))

    # Test my simpler implementation. I like this because it's simple, but it has some
    # bothersome rounding errors.
    for rounding in [ROUND_DOWN]:  # [ROUND_05UP, ROUND_DOWN, ROUND_UP, ROUND_CEILING, ROUND_FLOOR, ROUND_HALF_DOWN, ROUND_HALF_EVEN, ROUND_HALF_UP]:
        schedule = calculator.amortization_list(360, .06, 100000, '2019-10-01', rounding)
        payment = schedule[-1]
        print(payment.date, payment.beginning_principal, payment.interest, payment.payment, payment.ending_principal)

    # More robust implementation, slower, but rounding is very good.
    (table, summary) = calculator.amortization_df(.06, 30, 12, 100000)
    print(summary)
    print(table)

    # Just curious about the speed of the two payment calculations.
    import timeit
    print("NUMPY:", timeit.timeit(numpy_test, number=100000))
    print("NONUM:", timeit.timeit(no_numpy_test, number=100000))
