import ProFAST
import pandas as pd
import numpy as np
import time
from pkg_resources import resource_filename

class H2A_case():
    '''
        This class provides a wrapper for a H2A cases to be used in ProFAST 
        This is required because capacity scaling is not inherently built into ProFAST
        Instead, the scaling must be done a priori
    '''
    def __init__(self,case:str=None,verbose:bool=False):
        
        #   Filter H2A case chosen to point to the correct file. Other keywords are available (e.g. 'smr')
        case_compare = case.lower().replace('_',' ')
        if case_compare in ['central grid electrolysis','central grid electrolysis PEM','grid pem','pem']:
            self.h2a_file = 'central_grid_electrolysis_PEM'
        elif case_compare in ['central biomass gasification','biomass']:
            self.h2a_file = 'central_biomass_gasification'
        elif case_compare in ['central coal gasification w ccs','coal','coal ccs']:
            self.h2a_file = 'central_coal_gasification_w_ccs'
        elif case_compare in ['central grid electrolysis solid oxide','soec','grid soec']:
            self.h2a_file = 'central_grid_electrolysis_solid_oxide'
        elif case_compare in ['central natural gas reforming no ccs','smr no ccs','smr']:
            self.h2a_file = 'central_natural_gas_reforming_no_ccs'
        elif case_compare in ['central natural gas reforming w ccs','smr w ccs','atr','atr w ccs','atr ccs','smr ccs']:
            self.h2a_file = 'central_natural_gas_reforming_w_ccs'
        elif case_compare in ['central solar electrolysis','solar pem','solar electrolysis'] :
            self.h2a_file = 'central_solar_electrolysis'
        elif case_compare in ['central wind electrolysis','wind pem','wind electrolysis']:
            self.h2a_file = 'central_wind_electrolysis'
        else:
            self.h2a_file = 'central_grid_electrolysis_PEM'
        if verbose: print(f'H2A scenario chosen: {self.h2a_file}') 

        analysis_year = 2020

        self.pf = ProFAST.ProFAST(self.h2a_file)
        self.pf.set_params('analysis start year',analysis_year-3)
        self.feedstocks = self.pf.fs_df.loc[self.pf.fs_df['name'] != 'Var OpEX','name'].values

        #   Import scaling file
        self.load_cap_df()

        #   Set WACC - weight average cost of capital - usually fixed for the H2A cases
        self.WACC = 0.05669372

    def load_cap_df(self):
        
        cap_df = pd.read_csv(resource_filename(__name__, 'resources/capacity_scaling.csv'))
        cap_df = cap_df[['Nameplate kg/d','Technology','Year','Scaling Exponent','Capital Cost [$]','Capital recovery factor','Fixed Operating Cost [fraction of OvernightCapCost/y]','Variable Operating Cost [$/kg]','Aannualized replacement costs % of CapEx','Maximum Utilization [kg/kg]']]
        H2Atech = ['Central Biomass Gasification','Central Coal Gasification w/CCS','Central Grid Electrolysis (PEM)','Central Grid Electrolysis (Solid Oxide)','Central Natural Gas Reforming (no CCS)','Central Natural Gas Reforming w/CCS','Central Solar Electrolysis (PEM)','Central Wind Electrolysis (PEM)']
        cap_df = cap_df.loc[cap_df['Technology'].isin(H2Atech)].astype({'Nameplate kg/d':'float64','Capital Cost [$]':'float64'})
        self.cap_df = cap_df
        
    def get_cap_scaling(self,cap,year,sys_life,install_years):
        
        #   Filter the technology names to match what is in the capacity scaling df
        filtered_tech = {'central_natural_gas_reforming_w_ccs':'Central Natural Gas Reforming w/CCS','central_coal_gasification_w_ccs':'Central Coal Gasification w/CCS','central_biomass_gasification':'Central Biomass Gasification','central_grid_electrolysis_PEM':'Central Grid Electrolysis (PEM)'}
        #   Slim the df to the correct technology, less than the chosen year, and less than the chosen capacity
        tech_vals = self.cap_df.loc[(self.cap_df['Technology']==filtered_tech[self.h2a_file]) & (self.cap_df['Year']<=year) & (self.cap_df['Nameplate kg/d']<=cap)]
        
        #   Find the closest year that is less than the chosen year
        pick_year = tech_vals['Year'].max()
        #   Find the largest cap that is less than the chosen cap, but within the pick year
        pick_cap = tech_vals.loc[tech_vals['Year']==pick_year,'Nameplate kg/d'].max()

        #   This should narrow it to one row. Isolate the row and extract values
        pick_row = tech_vals.loc[(tech_vals['Year']==pick_year) & (tech_vals['Nameplate kg/d']==pick_cap)]
        pick_capex = pick_row['Capital Cost [$]'].iat[0]
        pick_scaling = pick_row['Scaling Exponent'].iat[0]
        pick_replace = pick_row['Aannualized replacement costs % of CapEx'].iat[0]
        pick_fixed_opex = pick_row['Fixed Operating Cost [fraction of OvernightCapCost/y]'].iat[0]
        pick_var_opex = pick_row['Variable Operating Cost [$/kg]'].iat[0]
        pick_util = pick_row['Maximum Utilization [kg/kg]'].iat[0]

        #   Calculate capex with embedded capital recovery factor
        capex_crf = pick_capex*(cap/pick_cap)**pick_scaling

        #   Calculate capital recovery factor
        #   For H2A-lite the weight average cost of capital is assumed constant
        #       WACC = per_eq*nom_irr+per_debt*debt_rate*(1-tax_rate) this will be affected by discount rate (nom_irr)
        #       WACC =  0.05669372 # For default H2Alite values
        crf = (self.WACC*(1+self.WACC)**sys_life)/((1+self.WACC)**sys_life-1)

        #   Calculate the capex without crf
        capex_no_crf = capex_crf/(1+install_years*crf)

        #   Replacement is a percentage of the capex
        replacement = pick_replace*capex_no_crf
        #   Fixed opex is a percentage of the capex
        fixed_opex = pick_fixed_opex*capex_no_crf
        #   The remaining fixed cost (replace + non_replace = fixed opex)
        non_replace_fixed = fixed_opex-replacement

        return [cap,capex_no_crf,non_replace_fixed,replacement,pick_var_opex,pick_util]

    def get_LCOH(self):
        sol = self.pf.solve_price()
        return sol['price']

    def adjust_cap(self,cap,analysis_year,sys_life,install_years):
        o_util = self.pf.vals['long term utilization']
        o_cap = self.pf.vals['capacity']
        o_capex = self.pf.capital_df.loc[self.pf.capital_df['name']=='Installed Capital','cost'].iat[0]
        o_replacement = self.pf.fixed_cost_df.loc[self.pf.fixed_cost_df['name']=='Annualized replacements','cost'].iat[0]
        o_non_replace_fixed = self.pf.fixed_cost_df.loc[self.pf.fixed_cost_df['name']=='fixed op ex','cost'].iat[0]
        o_var_opex = self.pf.fs_df.loc[self.pf.fs_df['name']=='Var OpEX','cost'].iat[0]
        # co2_cost_orig = self.pf.fixed_cost_df.loc[self.pf.fixed_cost_df['name']=='CCS','cost'].iat[0]
        original = [o_cap,o_capex,o_replacement,o_non_replace_fixed,o_var_opex,o_util]

        # capex,non_replace_fixed,replacement,var_opex,util=self.get_cap_scaling(cap,analysis_year,sys_life,install_years)
        # self.pf.set_params('capacity',cap)
        # self.pf.edit_capital_item('Installed Capital',{'cost':capex})
        # self.pf.edit_fixed_cost('Annualized replacements',{'cost':replacement})
        # self.pf.edit_fixed_cost('fixed op ex',{'cost':non_replace_fixed})
        # self.pf.edit_feedstock('Var OpEX',{'cost':var_opex})
        # self.pf.set_params('long term utilization',min(util,o_util))
        self.set_cap_adj_values(self.get_cap_scaling(cap,analysis_year,sys_life,install_years))

        price = self.get_LCOH()

        # self.pf.set_params('capacity',o_cap)
        # self.pf.edit_capital_item('Installed Capital',{'cost':o_capex})
        # self.pf.edit_fixed_cost('Annualized replacements',{'cost':o_replacement})
        # self.pf.edit_fixed_cost('fixed op ex',{'cost':o_non_replace_fixed})
        # self.pf.edit_feedstock('Var OpEX',{'cost':o_var_opex})
        # # self.pf.edit_fixed_cost('CCS',{'cost':co2})
        # self.pf.set_params('long term utilization',o_util)

        return (original,price)
    
    def set_cap_adj_values(self,values):
        o_cap,o_capex,o_replacement,o_non_replace_fixed,o_var_opex,o_util = values
        self.pf.set_params('capacity',o_cap)
        self.pf.edit_capital_item('Installed Capital',{'cost':o_capex})
        self.pf.edit_fixed_cost('Annualized replacements',{'cost':o_replacement})
        self.pf.edit_fixed_cost('fixed op ex',{'cost':o_non_replace_fixed})
        self.pf.edit_feedstock('Var OpEX',{'cost':o_var_opex})
        # self.pf.edit_fixed_cost('CCS',{'cost':co2})
        self.pf.set_params('long term utilization',o_util)

    def run_sensitivity(self,cap_values=None,regions=None,sens_params=[],sens_amount=[]):
        num_rows = len(cap_values)*len(regions)*len(sens_params)*len(sens_amount)+(len(cap_values)*len(regions))
        time_estimate = num_rows/7
        print(f'Estimated time for {num_rows} values: {round(time_estimate,2)}s')
        t0= time.time()
        saved_solution = []

        if cap_values == None:
            cap_values = [self.pf.vals['capacity']]
        if regions == None:
            regions = ['US Average']
        for cap in cap_values:
            analysis_year = self.pf.vals['analysis start year']
            sys_life = self.pf.vals['operating life']
            install_years = self.pf.vals['installation months']/12
            original,price = self.adjust_cap(cap,analysis_year,sys_life,install_years)
            
            #   Loop thru 
            for reg in regions:
                for fs in self.feedstocks:
                    self.pf.edit_feedstock(fs,{'cost':reg})
                
                #   Get LCOH without any sensitivity analysis
                sol = self.get_LCOH()
                saved_solution.append([self.h2a_file,cap,reg,'-',1,sol])
                # TODO: store value

                #   Loop thru sensitivity parameters
                for param in sens_params:
                    param_split = param.split('--')
                    if param_split[0] in self.feedstocks:
                        orignal = self.pf.fs_df.loc[self.pf.fs_df['name']==param_split[0],param_split[1]].iat[0]
                    else:
                        orignal = self.pf.vals[param]

                    #   Loop thru adjustment sensitivities
                    for adj in sens_amount:
                        if param_split[0] in self.feedstocks:
                            if param_split[1] == 'cost':
                                self.pf.edit_feedstock(param_split[0],{'cost':f'{adj}X {reg}'})
                            elif param_split[1] == 'usage':
                                self.pf.edit_feedstock(param_split[0],{'usage':adj*orignal})
                        else:
                            self.pf.set_params(param,adj*orignal)

                        #   Get LCOH of adjusted parameter
                        sol = self.get_LCOH()
                        saved_solution.append([self.h2a_file,cap,reg,param,adj,sol])

                #   Reset feedstocks
                for fs in self.feedstocks:
                    self.pf.edit_feedstock(fs,{'cost':'US Average'})

            #   Reset capacities
            self.set_cap_adj_values(original)
        
        print(f'{round(time.time()-t0,3)}s elapsed')

        return pd.DataFrame(saved_solution,columns=['scenario','capacity tpd','region','parameter','adj','LCOH'])
            

