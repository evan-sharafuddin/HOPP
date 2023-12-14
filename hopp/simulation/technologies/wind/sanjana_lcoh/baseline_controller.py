def get_loch():
        # Wind sites
        # TODO there is a lot of stuff here I don't need, such as the different sites, rated powers, and iterating over all those
        from optimization_utils_linear import baseline

        rated_powers = [1000]  # KW
        tf = 73
        total_time = 8760
        n_times_to_run = int(total_time / tf)

        switching_costs = [0]  # dont use and use
        farm_power = 1e6
        results = {}
        savings = {}
        sites = ["IN", "IA", "MS", "TX"]
        for site in sites:

            df = pd.read_csv(
                "wind_profiles/"
                + site
                + "_2020_Wind1000_Solar0_Storage0MWH_Storage0MW_TimeSeries.csv"
            )
            for rated_power in rated_powers:

                for switching_cost in switching_costs:
                    no_stacks = farm_power / (rated_power * 1e3)
                    no_stacks = int(no_stacks)
                    P_ = None
                    I_ = None
                    Tr_ = None
                    AC = 1
                    F_tot = 1
                    diff = 0
                    for start_time in range(n_times_to_run):
                        print(
                            f"Optimizing {no_stacks} stacks for {site} starting {start_time*tf}hr/{total_time}hr"
                        )
                        if start_time == 0:

                            df["Wind + PV Generation"].replace(0, np.NaN, inplace=True)
                            df = df.interpolate()

                        P_wind_t = (
                            df["Wind + PV Generation"][
                                (start_time * tf) : ((start_time * tf) + tf)
                            ].values
                            / 1e9
                            * farm_power
                        )
                        start = time.time()
                        P_tot_opt, P_, H2f, I_, Tr_, P_wind_t, AC, F_tot = baseline(
                            P_wind_t,
                            T=(tf),
                            n_stacks=(no_stacks),
                            c_wp=0,
                            c_sw=switching_cost,
                            rated_power=rated_power,
                            P_init=P_,
                            I_init=I_,
                            T_init=Tr_,
                            AC_init=AC,
                            F_tot_init=F_tot,
                        )
                        diff += time.time() - start
                        if type(AC).__module__ != "numpy":
                            AC = np.array(AC)
                            F_tot = np.array(F_tot)
                        if start_time == 0:
                            P_tot_opt_full = P_tot_opt
                            P_full = P_
                            P_wind_t_full = P_wind_t
                            H2f_full = H2f
                            I_full = I_
                            Tr_full = np.sum(Tr_, axis=0)
                            AC_full = AC
                            F_tot_full = F_tot

                        else:
                            P_tot_opt_full = np.vstack((P_tot_opt_full, P_tot_opt))
                            P_full = np.vstack((P_full, P_))
                            P_wind_t_full = np.vstack((P_wind_t_full, np.transpose(P_wind_t)))
                            H2f_full = np.vstack((H2f_full, H2f))
                            I_full = np.vstack((I_full, I_))
                            Tr_full = np.vstack((Tr_full, np.sum(Tr_, axis=0)))
                            AC_full = np.vstack((AC_full, (AC)))
                            F_tot_full = np.vstack((F_tot_full, (F_tot)))

                    results[f"{site}_{rated_power}kW_{switching_cost}_P_tot"] = P_tot_opt_full
                    results[f"{site}_{rated_power}kW_{switching_cost}_P_ind"] = P_full
                    results[f"{site}_{rated_power}kW_{switching_cost}_H2f"] = H2f_full
                    results[f"{site}_{rated_power}kW_{switching_cost}_ONOFF"] = I_full
                    results[f"{site}_{rated_power}kW_{switching_cost}_Tr"] = Tr_full
                    results[f"{site}_{rated_power}kW_{switching_cost}_P_wind_t"] = (
                        df["Wind + PV Generation"].values / 1e9 * farm_power
                    )
                    results[f"{site}_{rated_power}kW_{switching_cost}_AC"] = AC_full
                    results[f"{site}_{rated_power}kW_{switching_cost}_F_tot"] = F_tot_full
                    results[f"{site}_{rated_power}kW_{switching_cost}_comp_time"] = diff
        

        from replacement_cost import EL_Cost_Schnuelle
        ec_schnuelle = EL_Cost_Schnuelle(stack_rating_kW=rated_power)
        C_INV = ec_schnuelle.get_capex() * ec_schnuelle.conversion
        C_SW = ec_schnuelle.get_onoff_cost() * ec_schnuelle.conversion

        LC = C_INV * num_stacks + C_SW * num_on_off # note: num_on_off = T in the optimization formulation

        LCOH = LC / H2_prod 

        return LCOH