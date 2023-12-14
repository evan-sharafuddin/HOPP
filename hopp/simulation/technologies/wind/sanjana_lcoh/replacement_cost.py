import numpy as np


class EL_Cost_Schnuelle:
    """
    [1] C. Schnuelle, T. Wassermann, D. Fuhrlaender, and E. Zondervan, “Dynamic hydrogen
    production from PV & wind direct electricity supply - Modeling and techno-economic
    assessment,” International Journal of Hydrogen Energy, vol. 45, no. 55,
    pp. 29938-29952, Nov. 2020, doi: 10.1016/j.ijhydene.2020.08.044.

    [2] Z. Tully, G. Starke, K. Johnson, and J. King, “An Investigation of Heuristic 
    Control Strategies for Multi-Electrolyzer Wind-Hydrogen Systems Considering 
    Degradation,” in 2023 IEEE Conference on Control Technology and Applications (CCTA), 
    Aug. 2023, pp. 817-822. doi: 10.1109/CCTA54093.2023.10252187.

    This class gives costs in 2020 euros

    """

    def __init__(self, stack_rating_kW):
        self.stack_rating = stack_rating_kW
        self._initialize_constants()

    def _initialize_constants(self):
        # Schnuelle Table 5: PEM column
        self.C = 860  # [euro/kW] acquistion costs, total
        self.C_stack = 0.48 * self.C  # [euro/kW] stack acquisition costs
        self.C_bop = (
            self.C - self.C_stack
        )  # [euro/kW] balance of plant cquisition costs
        self.K_sam = 13  # [euro/(a kW)] service and maintenance costs, annual
        self.OP = 44200  # [hr] stack overhaul period
        self.SL = 20  # [a] system lifetime in years
        self.IR = 0.05  # interest rate 5%
        self.K_h20 = 1  # [euro/m^3] cost of deionized water
        self.K_tai = 0.02  # [a^-1] taxes and insurance

        # Schnuelle Table 6
        self.K_el_pv_no_sur = 4.5 # [ct/kWh] PV procurment cost without EEG surcharge
        self.K_el_pv_sur = 5.8 # [ct/kWh] PV procurement cost with EEG surcharge
        self.K_el_wind_onshore_no_sur = 9.3 # [ct/kWh] onshore wind procurement cost without EEG surcharge
        self.K_el_wind_onshore_sur = 10.6 # [ct/kWh] onshore wind procurment cost with EEG surchage
        self.K_el_wind_offshore_no_sur = 15.4 # [ct/kWh] offshore wind procurement cost without EEG surcharge
        self.K_el_wind_offshore_sur = 16.7 # [ct/kWh] offshore wind procurement cost with EEG surcharge

        # Schneulle from text pg. 7
        self.RF = 1.54 # ratio factor to account for "installation, yard improvements, legal expense, contractor fees, and contingencies"
        self.OH = 0 # [hr] operating hours, depends on the specific scenario

        # Tully degradation parameters
        self.r_s = 1.41737929e-10  # steady degradation rate
        self.r_f = 3.33330244e-07  # fluctuating degradation rate
        self.r_o = 1.47821515e-04  # on/off degradation rate
        self.d_eol = 0.721176975037  # [V] amount of degradation at end of life

        self.replacement_onoff = (
            self.d_eol / self.r_o
        )  # number of on/off cycles to fully degrade the stack

        # Currency conversion
        # https://www.in2013dollars.com/europe/inflation/2020?amount=1000
        self.euro2020_to_euro2023 = 1.2416 # [euro2023/euro2020]

        # https://www.exchangerates.org.uk/EUR-USD-spot-exchange-rates-history-2023.html#:~:text=Average%20exchange%20rate%20in%202023%3A%201.0834%20USD.
        self.euro2023_to_USD2023 = 1.0834 # [USD/euro] in 2023

        self.conversion = self.euro2020_to_euro2023 * self.euro2023_to_USD2023

    def get_capex(self):
        """
        Calculate the capital expenditure of investment cost
        """

        capex = self.RF * (self.C_stack + self.C_bop) * self.stack_rating
        return capex

    def get_SR(self):
        """
        Calculate the cost to replace a stack
        """

        # Schnuelle eqn. 26
        # Schnuelle calculates the cost of replacements during a certain time period 
        # even if the stack is not replaced during that time period
        self.K_r = (
            self.C_stack / self.SL * (self.SL * self.OH / self.OP - 1)
        )  # [euro/(a kW)] annual cost of stack replacement

        return self.C_stack * self.stack_rating

    def get_onoff_cost(self):
        """
        Calculate the cost of a single on/off cycle
        """
        n_cycles = (self.d_eol / self.r_o)  # number of on/off cycles to fully degrade the stack
        C_onoff = self.get_SR() / n_cycles
        return C_onoff

    def get_WP_cost(self):
        """
        calculate the cost of wind power
        """

        # EEG surcharge is only in Germany so choose the wind cost without 
        return self.K_el_wind_onshore_no_sur


    def get_opex(self):
        """
        calculate operational expenditures
        """
        # opex = V_h20 * self.K_h20 + W_el * self.K_el + P_N * self.K_sam + self.get_capex() + P_N * self.K_r # [euro/a] annual opex
        opex = -1
        return opex

    def get_NPC(self):
        """
        calculate net present cost of the plant output
        """
        pass


class EL_Cost_Singlitico:
    # This class is erronious do not use

    def __init__(self, stack_rating_kW):
        self.P_elec = stack_rating_kW

        self._initialize_constants()

    def _initialize_constants(self):
        # ======= H2@Scale Degradation Model ======= #
        self.r_s = 1.41737929e-10  # steady degradation rate
        self.r_f = 3.33330244e-07  # fluctuating degradation rate
        self.r_o = 1.47821515e-04  # on/off degradation rate
        self.d_eol = 0.721176975037  # [V] amount of degradation at end of life

        self.replacement_onoff = (
            self.d_eol / self.r_o
        )  # number of on/off cycles to fully degrade the stack

        # ======= Singlitico Values ======= #

        # A. Singlitico, J. Østergaard, and S. Chatzivasileiadis, “Onshore, offshore or
        # in-turbine electrolysis? Techno-economic overview of alternative integration designs
        # for green hydrogen production into Offshore Wind Power Hubs,” Renewable and
        # Sustainable Energy Transition, vol. 1, p. 100005, Aug. 2021,
        # doi: 10.1016/j.rset.2021.100005.

        # fromo Table B.2
        self.RC_elec = 600  # [euro/kW] reference cost
        self.IF = 0.33  # [% RC_elec] installation factor
        self.RP_elec = 10  # [MW] reference power
        self.SF_elec = -0.24  # if P_elec < 10 MW, use -0.14 if P_elec > 10 MW

        # from Table B.3
        self.RU_sr = 0.41  # [%] Reference cost share for a reference power RP_sr = 5 MW
        self.P_stack_max = 2  # [MW] average max stack size
        self.SF_sr_0 = 0.11  # average scale factor

        self.P_elec_bar = 1  # [GW]
        self.RP_sr = 5  # [MW] stack replacement reference power

        # not sure what this term really does but Zack is assuming that the stack is not replaced before it is fully degraded
        self.OH = 1  # operating hours
        self.OH_max = 1  # lifetime operating hours

        self.OS = 0  # 1 if offshore or 0 if electrolyzer is installed onshore

    def get_SR_Cost(self):
        """
        Output:
        onoff_cycle_cost - cost of a single onoff cycle in 2017 USD
        stack_replacement_cost - stack replacement cost in 2017 USD
        """

        # Electrolyzer capex "non-equipment costs"
        capex_el = (
            self.P_elec
            * self.RC_elec
            * (1 + self.IF * self.OS)
            * ((self.P_elec * 1e-3) / self.RP_elec) ** self.SF_elec
        )

        # Electrolyzer opex planned and unplanned maintenance labor cost
        opex_el_eq = (
            capex_el
            * (1 - self.IF * (1 + self.OS))
            * 0.0344
            * (self.P_elec * 1e-3) ** (-0.155)
        )

        # Electrolyzer stack cost and replacement cost
        SF_sr = 1 - (1 - self.SF_sr_0) * np.exp(-self.P_elec_bar / self.P_stack_max)
        RC_sr = (
            self.RU_sr
            * self.RC_elec
            * (1 - self.IF)
            * (self.RP_sr / self.RP_elec) ** self.SF_elec
        )
        opex_el_sr = (
            self.P_elec
            * RC_sr
            * ((self.P_elec * 1e-3) / (self.RP_sr)) ** SF_sr
            * (self.OH / self.OH_max)
        )

        # Electrolyzer opex site management, rent, etc.
        opex_elec_neq = 0.04 * capex_el * self.IF * (1 + self.OS)

        # cost of a single onoff cycle in euros
        C_SD_singlitico = opex_el_sr / self.replacement_onoff

        # https://www.exchangerates.org.uk/EUR-USD-spot-exchange-rates-history-2017.html#:~:text=This%20is%20the%20Euro%20(EUR,USD%20on%2003%20Jan%202017.
        # average exchange rate in 2017
        ex_rate = 1.1304  # [euro/USD]

        stack_replacement_cost = opex_el_sr / ex_rate
        onoff_cycle_cost = C_SD_singlitico / ex_rate

        # print("The stack replacement cost is: ", opex_el_sr / ex_rate, "(USD 2017) from singlitico")
        # print("The cost of a shutdown is:", C_SD_singlitico / ex_rate, "(USD 2017) using singlitico et al 2021 numbers")

        return stack_replacement_cost, onoff_cycle_cost

    def get_INV_cost(self):
        capex_el = (
            self.P_elec
            * self.RC_elec
            * (1 + self.IF * self.OS)
            * ((self.P_elec * 1e3) / self.RP_elec) ** self.SF_elec
        )

        return capex_el


if __name__ == "__main__":
    stack_rating_kW = 500 # [kW]

    # ec_sing = EL_Cost_Singlitico(stack_rating_kW)
    # C_SR, C_SW = ec_sing.get_SR_Cost()
    # C_INV = ec_sing.get_INV_cost()

    # print("Singlitico et al.")
    # print(
    #     f"Stack replacement cost: {C_SR}\nStack on/off cost: {C_SW}\nStack INV cost: {C_INV}"
    # )

    ec_schnuelle = EL_Cost_Schnuelle(stack_rating_kW)
    C_SR = ec_schnuelle.get_SR() * ec_schnuelle.conversion
    C_SW = ec_schnuelle.get_onoff_cost() * ec_schnuelle.conversion
    C_INV = ec_schnuelle.get_capex() * ec_schnuelle.conversion
    C_WP = ec_schnuelle.get_WP_cost() * ec_schnuelle.conversion

    print("\nSchnuelle et al.")
    print(
        f"Stack replacement cost: {C_SR}\nStack on/off cost: {C_SW}\nStack INV cost: {C_INV}\nWind cost: {C_WP}"
    )



    # Very rough LCOH calculations

    H2_gen = 2e6 # kg
    H2_eff = 55 # kWh / kg 
    H2_elec = H2_gen * H2_eff
    LCOE = 30 # $ / MWh

    C_elec = LCOE * H2_elec / 1e3
    C_onoff = 50000
    
    h20 = 17875 # kg
    
    C_h20 = 1 * h20

    LT = 30

    LCOH = (C_elec + C_onoff + C_INV/LT + C_h20) / H2_gen

    print(f"LCOH: {LCOH}")
