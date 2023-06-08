import pandas as pd
import numpy as np
import numpy_financial as npf
import matplotlib.pyplot as plt
import math, json, time, warnings
from matplotlib import patches as mpatches
import plotly.graph_objects as go
import plotly.express as px

from pkg_resources import resource_filename

#TODO: h2 price array

class ProFAST():
    """
    A class to represent a ProFAST scenario
    
    Attributes
    ----------
    vals : dict
        Dictionary of all variables 
    fs_df : Pandas Dataframe
        Pandas dataframe for any feedstocks
    coprod_df : Pandas Dataframe
        Pandas dataframe for any coproducts
    fixed_cost_df : Pandas Dataframe
        Pandas dataframe for any fixed costs
    capital_df : Pandas Dataframe
        Pandas dataframe for any capital items
    incentive_df : Pandas Dataframe
        Pandas dataframe for any incentives

    Methods
    -------
    load_json(file):
        Import a scenario from a JSON formatted input file
    set_params(name,value):
        Set parameter <name> to <value>
    load_MACRE_table():
        Load in MACRS depreciation table from csv
    add_capital_item(name,cost,depr_type,depr_period,refurb):
        Add a capital item 
    add_feedstock(name,usage,unit,cost,escalation):
        Add a feedstock (expense)
    add_coproduct(name,usage,unit,cost,escalation):
        Add a coproduct (revenue)
    add_fixed_cost(name,usage,unit,cost,escalation):
        Add a fixed cost (expense)
    add_incentive(name,value,decay,sunset_years)
        Add an incentive (revenue)
    edit_capital_item(name,value):
    edit_feedstock(name,value):
    edit_coproduct(name,value):
    edit_fixed_cost(name,value):
    edit_incentive(name,value):
    remove_capital_item(name):
    remove_feedstock(name):
    remove_coproduct(name):
    remove_fixed_cost(name):
    remove_incentive(name):
    update_sales(sales,analysis_year,analysis_length,yrs_of_operation,fraction_of_year_operated):
        Update all revenue streams with sale of commodities and capital expenditures
    clear_values(class_type)
        Clears <class_type> of all entries (i.e. feedstock)
    plot_cashflow:
        Plots the investor cash flow
    plot_costs:
        Plot cost of goods breakdown
    plot_time_series()
        Plot yearly values in plotly
    plot_costs_yearly:
        Plot cost breakdown per year
    plot_costs_yearly2:
        Plot cost breakdown per year in interavtive plotly
    cash_flow(price=None)
        Calculate net present value using commodity price of <price>
    solve_price():
        Solve for commodity price when net present value is zero
    loan_calc(un_depr_cap,net_cash_by_investing,receipt_one_time_cap_incentive,all_depr,earnings_before_int_tax_depr,annul_op_incent_rev,total_revenue,total_operating_expenses,net_ppe):
        Calculate the financial loan amounts
    depreciate(type,period,percent,cap,qpis,ypis):
        Depreciates an item following MACRS or Straight line
    """
    def __init__(self,case=None):
        '''
        Initialization of ProFAST class

        Parameters:
        -----------
        case=None : string
            String to denote a premade json file in the resources folder
        '''
        #   Initialize dataframes and variables
        self.vals={}
        self.fs_df = pd.DataFrame(columns=['name','usage','unit','cost','escalation'])
        self.coprod_df = pd.DataFrame(columns=['name','usage','unit','cost','escalation'])
        self.fixed_cost_df = pd.DataFrame(columns=['name','usage','unit','cost','escalation'])
        self.capital_df = pd.DataFrame(columns=['name','cost','depr_type','depr_period','refurb'])
        self.incentive_df = pd.DataFrame(columns=['name','value','decay','sunset_years','tax_credit'])
        self.val_names = ['capacity','installation cost','non depr assets','end of proj sale non depr assets','maintenance',
                        'one time cap inct','annual operating incentive','incidental revenue','commodity',
                        'analysis start year','operating life','installation months','demand rampup','long term utilization',
                        'TOPC','credit card fees','sales tax','road tax','labor','license and permit','rent',
                        'property tax and insurance percent','admin expense percent','total income tax rate',
                        'capital gains tax rate','operating incentives taxable','sell undepreciated cap',
                        'tax losses monetized','tax loss carry forward years','general inflation rate',
                        'leverage after tax nominal discount rate','debt equity ratio of initial financing',
                        'debt type','loan period if used','debt interest rate','cash onhand percent']

        #   Load in CSV resources - MACRS table and region feedstock costs
        self.load_MACRS_table()
        self.load_feedstock_costs()

        #   Load in default values for variables if no case is specified
        self.default_values = self.vals
        if case == None:
            self.load_json('blank')
        else:
            self.load_json(case) # Load variables from json file

    def load_json(self,case:str):
        '''
        Overview:
        ---------
            Load a ProFAST scenario based on a json case file

        Parameters:
        -----------
            case:str - The case file name e.g. central_grid_electrolysis_PEM
        '''
        # Clear out any pre existing values then read the new file
        #  TODO: check if file exists first
        self.clear_values('all')
        f = open(resource_filename(__name__, f'resources/{case}.json'))
        # f = open(f'{self.__location__}/../resources/{case}.json')
        data = json.load(f)

        # Load variables,feedstocks,coprods,fixed_costs,capital,incentives
        vars = data['variables']
        for i in vars:
            self.set_params(i,vars[i])
        if 'feedstock' in data:
            vars = data['feedstock']
            for i in vars:
                self.add_feedstock(i["name"],i["usage"],i["unit"],i["cost"],i["escalation"])
        if 'coproduct' in data:
            vars = data['coproduct']
            for i in vars:
                self.add_coproduct(i["name"],i["usage"],i["unit"],i["cost"],i["escalation"])
        if 'fixed cost' in data:
            vars = data['fixed cost']
            for i in vars:
                self.add_fixed_cost(i["name"],i["usage"],i["unit"],i["cost"],i["escalation"])
        if 'capital item' in data:
            vars = data['capital item']
            for i in vars:
                self.add_capital_item(i["name"],i["cost"],i["depr type"],i["depr period"],i["refurb"])
        if 'incentive' in data:
            vars = data['incentive']
            for i in vars:
                self.add_incentive(i["name"],i["value"],i["decay"],i["sunset years"],i["tax credit"])

    def set_params(self,name:str,value):
        '''
            Set ProFAST scenario parameters:

            Parameters:
            -----------
            name : string
                Name of the pameter to change
                Valid options are: 
                    capacity : float
                    installation cost : {value:float, depr type:"MACRS" or "Straight line", depr period:float, depreciable:bool}
                    non depr assets : float
                    end of proj sale non depr assets : float
                    maintenance : {value:float ,escalation:float}
                    one time cap inct : {value:float, depr type:"MACRS" or "Straight line", depr period:float, depreciable:bool}
                    annual operating incentive : {value:float ,decay:float, sunset years: int}
                    incidental revenue : {value:float, escalation:float}
                    commodity : {name:string, initial price:float, unit:string, escalation:float}
                    analysis start year : int
                    operating life : int
                    installation months : int
                    demand rampup : float
                    long term utilization : float
                    TOPC : {unit price:float, decay:float, support utilization:float, sunset years:int}
                    credit card fees : float
                    sales tax : float
                    road tax : {value:float, escalation:float}
                    labor : {value:float, rate:float, escalation:float}
                    license and permit : {value:float, escalation:float}
                    rent : {value:float, escalation:float}
                    property tax and insurance percent : float
                    admin expense percent : float
                    total income tax rate : float
                    capital gains tax rate : float
                    operating incentives taxable : bool
                    sell undepreciated cap : bool
                    tax losses monetized : bool
                    tax loss carry forward years : int
                    general inflation rate : float
                    leverage after tax nominal discount rate : float
                    debt equity ratio of initial financing : float
                    debt type : "Revolving debt" or "One time loan"
                    loan period if used : int
                    debt interest rate : float
                    cash onhand percent : float
        '''
        # Check if it is a valid variable name
        if name not in self.val_names:
            warnings.warn(name + ' is not a valid variable!',stacklevel=2)
            return
        if name == 'long term utilization': # prevents over 100% utilization to be consistent with ProFAST
            if value>1:
                value = 1

        #   Set these to integers      
        if name == 'installation months': # TODO - should this be limited to int?
            value = np.floor(value)
        if name == 'tax loss carry forward years':
            value = int(value)
        if name in ['TOPC','annual operating incentive']:
            value['sunset years'] = np.floor(value['sunset years'])
        # Filter depreciation values
        if name in ['one time cap inct','installation cost']:
            if(value['depr type']=='MACRS'):
                closest_year = value['depr period']
                if value['depr period'] not in [3,5,7,10,15,20]:
                    closest_year = min([3,5,7,10,15,20], key=lambda x:abs(x-value['depr period']))
                    warnings.warn(str(value['depr period']) + ' is not a valid MACRS depreciation period! Value was reset to '+str(closest_year) ,stacklevel=2)
                value['depr period'] = int(closest_year)
            elif (value['depr type']=='Straight line'):
                value['depr period'] = int(np.floor(value['depr period']))
            else:
                warnings.warn(str(value['depr type']) + ' is not a valid depreciation type! Try MACRS or Straight line',stacklevel=2)

        self.vals[name] = value

    def load_MACRS_table(self):
        '''
        Read in MACRS depreciation table
        '''
        self.MACRS_table = pd.read_csv(resource_filename(__name__, 'resources/MACRS.csv'))

    def load_feedstock_costs(self):
        '''
        Load in AEO2022 regional feedstock costs
        '''
        self.regional_feedstock = pd.read_csv(resource_filename(__name__, 'resources/regional_feedstock_costs.csv'))
        self.all_feedstock_regions = self.regional_feedstock['cost_formatted'].unique()
        self.regional_feedstock_names = self.regional_feedstock['name'].unique()

    def add_capital_item(self,name:str,cost:float,depr_type:str,depr_period:str,refurb:list):
        '''
        Overview:
        ---------
            Add a capital expenditure

        Parameters:
        -----------
            name:str - Name of the capital item
            cost:float - Cost of the capital item in start year dollars
            depr_type:str - Depreciation type, must be MACRS or Straight line
            depr_period:int - Depreciation period, if MACRS, must be 3, 5, 7, 10, 15, or 20
            refurb:list[float] - Array of refubishment fractions (e.g. [0,0.1,0,0,0.5,0.1])
        '''
        
        #   Error checking input values for depreciation
        if depr_type.lower() not in ['macrs','straight line']:
            warnings.warn(f'{depr_type} is not a valid depreciation type! Capital item was not added. Try MACRS or Straight line' ,stacklevel=2)
            return
        if depr_type.lower() == 'macrs':
            MACRS_years = [3,5,7,10,15,20]
            if depr_period not in MACRS_years:
                closest_year = min(MACRS_years, key=lambda x:abs(x-depr_period))
                warnings.warn(f'{depr_period} is not a valid MACRS depreciation period! Value was reset to {closest_year}' ,stacklevel=2)
        if not isinstance(refurb,list):
            warnings.warn(f'{refurb} must be a list! Capital item was not added. Try [0]' ,stacklevel=2)
            return
        
        new_row = pd.DataFrame(data={'name':str(name),'cost':float(cost),'depr_type':depr_type,'depr_period':int(depr_period),'refurb':0},index=[0])
        dt = {'name':'str','cost':'float64','depr_type':'category','depr_period':'int8','refurb':'object'}
        new_row = new_row.astype(dt)
        new_row.at[0,'refurb'] = refurb
        self.capital_df = pd.concat([self.capital_df,new_row],ignore_index=True)

    def add_feedstock(self,name:str,usage:float,unit:str,cost,escalation:float):
        '''
        Overview:
        ---------
            Add a feedstock expense

        Parameters:
        -----------
            name:str - Name of the feedstock
            usage:float - Usage of feedstock per unit of commondity
            unit:str - Unit for feedstock quantity (e.g. kg) only used for reporting
            cost:str or list or dict - Cost of the feedstock in nominal $ per unit of feedstock
            escalation:float - Yearly escalation of feedstock price
        '''
        #   Check if cost is a str, then check if it is a valid regional feedstock
        if isinstance(cost,str):  
            check_cost = cost
            if 'X' in check_cost:
                check_cost = check_cost.split('X')[1].strip()
            if not (check_cost in self.all_feedstock_regions):
                warnings.warn(cost + ' is not a valid region!',stacklevel=2)
                return
            if not (name in self.regional_feedstock_names):
                warnings.warn(name + ' is not a valid feedstock!',stacklevel=2)
                return

        new_row = pd.DataFrame({'name':str(name),'usage':0.0,'unit':str(unit),'escalation':float(escalation),'cost':0.0},index=[0])
        dt = {'name':'str','usage':'object','unit':'str','escalation':'float64','cost':'object'}
        new_row = new_row.astype(dt)
        new_row.at[0,'cost']=cost
        new_row.at[0,'usage']=usage
        if isinstance(cost,list) | isinstance(cost,str) | isinstance(cost,dict):
            new_row.at[0,'escalation'] = 0.0
        self.fs_df = pd.concat([self.fs_df,new_row],ignore_index=True)
    
    def add_coproduct(self,name:str,usage:float,unit:str,cost,escalation:float):
        '''
        Overview:
        ---------
            Add a coproduct recenue

        Parameters:
        -----------
            name:str - Name of the feedstock
            usage:float - Usage of feedstock per unit of commondity
            unit:str - Unit for feedstock quantity (e.g. kg) only used for reporting
            cost:str or list or dict - Cost of the feedstock in nominal $ per unit of coproduct
            escalation:float - Yearly escalation of feedstock price
        '''
        #   TODO add variable usage
        new_row = pd.DataFrame({'name':str(name),'usage':float(usage),'unit':str(unit),'escalation':float(escalation),'cost':0},index=[0])
        dt = {'name':'str','usage':'float64','unit':'str','escalation':'float64','cost':'object'}
        new_row = new_row.astype(dt)
        new_row.at[0,'cost']=cost
        if isinstance(cost,list):
            new_row.at[0,'escalation'] = 0.0
        self.coprod_df = pd.concat([self.coprod_df,new_row],ignore_index=True)

    def add_fixed_cost(self,name:str,usage:float,unit:str,cost:float,escalation:float):
        '''
        Overview:
        ---------
            Add a yearly fixed cost

        Parameters:
        -----------
            name:str - Name of the fixed cost
            usage:float - Usage multiplier - default to 1
            unit:str - Unit of fixed cost ($)
            cost:float - Yearly cost ($)
            escalation:float - Yearly escalation of fixed cost
        '''
        new_row = pd.DataFrame({'name':str(name),'usage':float(usage),'unit':str(unit),'cost':float(cost),'escalation':float(escalation)},index=[0])
        self.fixed_cost_df = pd.concat([self.fixed_cost_df,new_row],ignore_index=True)

    def add_incentive(self,name:str,value:float,decay:float,sunset_years:int,tax_credit:bool):
        '''
        Overview:
        ---------
            Add a per unit commodity incentive

        Parameters:
        -----------
            name:str - Name of the incentive
            value:float - Value of incentive ($)
            decay:float - Yearly decay of incentive (fraction), negative is escalation
            sunset_years:int - Duration of incentive (years)
            tax_credit:bool - Is incentive treated as tax credit or revenue
        '''

        new_row = pd.DataFrame({'name':name,'value':float(value),'decay':float(decay),'sunset_years':sunset_years,'tax_credit':tax_credit},index=[0])
        self.incentive_df = pd.concat([self.incentive_df,new_row],ignore_index=True)

    def edit_feedstock(self,name:str,value:dict):
        '''
        Overview:
        ---------
            Edit the values of feedstock

        Parameters:
        -----------
            name:str - Name of the feedstock to edit
            value:dict - name,value pairs for parameter to edit 
        '''
        #   Loop thru the supplied dictionary
        for key,val in value.items():
            if not (key in self.fs_df.columns): # Check if it is a valid value
                warnings.warn(key + ' is not a valid value to edit!',stacklevel=2)
                return
            if not (self.fs_df['name']==name).any(): # Check if the feedstock name exists
                warnings.warn(name + ' does not exist!',stacklevel=2)
                return
            if key=='Cost' and isinstance(val,str): # If using a string, check that the region is valid 
                check_value = val
                if 'X' in check_value:
                    check_value = check_value.split('X')[1].strip()  
                if not (check_value in self.all_feedstock_regions):
                    warnings.warn(val + ' is not a valid region!',stacklevel=2)
                    return 

            self.fs_df.loc[self.fs_df['name']==name,key] = val

    def edit_coproduct(self,name:str,value:dict):
        '''
        Overview:
        ---------
            Edit the values of coproduct

        Parameters:
        -----------
            name:str - Name of the coproduct to edit
            value:dict - name,value pairs for parameter to edit 
        '''
        for key,val in value.items():
            if key in self.coprod_df.columns:
                self.coprod_df.loc[self.coprod_df['name']==name,key] = val

    def edit_capital_item(self,name:str,value:dict):
        '''
        Overview:
        ---------
            Edit the values of capital

        Parameters:
        -----------
            name:str - Name of the capital to edit
            value:dict - name,value pairs for parameter to edit 
        '''
        for key,val in value.items():
            if key in self.capital_df.columns:
                self.capital_df.loc[self.capital_df['name']==name,key] = val

    def edit_fixed_cost(self,name:str,value:dict):
        '''
        Overview:
        ---------
            Edit the values of fixed cost

        Parameters:
        -----------
            name:str - Name of the fixed cost to edit
            value:dict - name,value pairs for parameter to edit 
        '''
        
        for key,val in value.items():
            if key in self.fixed_cost_df.columns:
                self.fixed_cost_df.loc[self.fixed_cost_df['name']==name,key] = val

    def edit_incentive(self,name:str,value:dict):
        '''
        Overview:
        ---------
            Edit the values of incentive

        Parameters:
        -----------
            name:str - Name of the incentive to edit
            value:dict - name,value pairs for parameter to edit 
        '''
        
        for key,val in value.items():
            if key in self.incentive_df.columns:
                self.incentive_df.loc[self.incentive_df['name']==name,key] = val

    def remove_capital_item(self,name:str):
        '''
        Overview:
        ---------
            Delete a capital item

        Parameters:
        -----------
            name:str - Name of the capital to delete
        '''
        
        self.capital_df = self.capital_df.loc[self.capital_df['name'] != name]

    def remove_feedstock(self,name:str):
        '''
        Overview:
        ---------
            Delete a feedstock item

        Parameters:
        -----------
            name:str - Name of the feedstock to delete
        '''
        self.fs_df = self.fs_df.loc[self.fs_df['name'] != name]

    def remove_coproduct(self,name:str):
        '''
        Overview:
        ---------
            Delete a coproduct item

        Parameters:
        -----------
            name:str - Name of the coproduct to delete
        '''
        self.coprod_df = self.coprod_df.loc[self.coprod_df['name'] != name]

    def remove_fixed_cost(self,name:str):
        '''
        Overview:
        ---------
            Delete a fixed cost item

        Parameters:
        -----------
            name:str - Name of the fixed cost to delete
        '''
        self.fixed_cost_df = self.fixed_cost_df.loc[self.fixed_cost_df['name'] != name]

    def remove_incentive(self,name:str):
        '''
        Overview:
        ---------
            Delete a incentive item

        Parameters:
        -----------
            name:str - Name of the incentive to delete
        '''
        self.incentive_df = self.incentive_df.loc[self.incentive_df['name'] != name]

    def update_sales(self,analysis_length,yrs_of_operation):
        ''''
        Overview:
        ---------
            Update the feedstock,capital,coproduct,incentive and fixed cost dataframes based on commodity sales

        Parameters:
        -----------
            analysis_length:
            yrs_of_operation:
        '''
        #   Pull in parameters
        sales = self.yearly_sales
        analysis_year = np.arange(0, analysis_length+1)
        fraction_of_year_operated = yrs_of_operation-np.concatenate(([0], yrs_of_operation[: -1]))
        
        #   Update feedstock DF
        #       If no feedstocks, set expenses to 0
        if len(self.fs_df.index) == 0:
            self.fs_df['expense'] = 0
            self.fs_expense = 0
        else:
            #   If a dictionary is supplied for 'usage' then turn it into a list and multiply by the sales. If not a dictionary, multiply the usage by sales
            year_cols = list(map(str,self.calendar_year))
            self.fs_df['sales'] = self.fs_df['usage'].apply(lambda x: np.multiply([x[y] for y in year_cols],sales) if isinstance(x,dict) else x*sales)
            
            #   If a string such as '2X US Average' is used, then separate out the multiplier ('2'). Otherwise set multiplier to 1
            self.fs_df['multiplier'] = self.fs_df['cost'].apply(lambda x: np.array([float(x.split('X')[0].strip())]*len(analysis_year)) if isinstance(x,str) and 'X' in x else  np.array([1.0]*len(analysis_year)))
            self.fs_df['cost_formatted'] = self.fs_df['cost'].apply(lambda x: x.split('X')[1].strip() if isinstance(x,str) and 'X' in x else ([x[y] for y in year_cols] if isinstance(x,dict) else x) )

            if self.fs_df['cost_formatted'].isin(self.all_feedstock_regions).any():
                
                self.regional_feedstock['value_per_unit'] = self.regional_feedstock.loc[:,year_cols].values.tolist()
                regional_inputs = self.fs_df.loc[self.fs_df['cost_formatted'].apply(lambda x: isinstance(x,str)),['name','usage','unit','cost','cost_formatted','escalation','sales','multiplier']]
                leftover = self.fs_df[self.fs_df['cost_formatted'].apply(lambda x: not isinstance(x,str))]
                self.fs_df = regional_inputs.merge(self.regional_feedstock[['name','cost_formatted','value_per_unit']],on=['name','cost_formatted'],how='left')
                self.fs_df = pd.concat((self.fs_df,leftover))
            
            self.fs_df.loc[~ self.fs_df['cost_formatted'].isin(self.all_feedstock_regions),'value_per_unit'] = self.fs_df.loc[~ self.fs_df['cost_formatted'].isin(self.all_feedstock_regions)].apply(lambda x: x['cost_formatted']*(1.0+x['escalation'])**(analysis_year-1),axis=1)
            
            self.fs_df['value_per_unit'] =self.fs_df['value_per_unit'].values*self.fs_df['multiplier'].values

            self.fs_df['expense']=self.fs_df['sales'].values*self.fs_df['value_per_unit'].values

            self.fs_expense = self.fs_df['expense'].sum()

        #   Update coprod DF
        #       If no feedstocks, set revenue to 0
        if len(self.coprod_df.index) == 0:
            self.coprod_df['revenue'] = 0
            self.coprod_revenue = 0
        else:
            self.coprod_df['sales'] = self.coprod_df['usage'].apply(lambda x:x*sales)
            self.coprod_df['value_per_unit'] = self.coprod_df.apply(lambda x: x['cost']*(1.0+x['escalation'])**(analysis_year-1),axis=1)
            self.coprod_df['revenue'] = self.coprod_df.apply(lambda x: x['sales']*x['value_per_unit'],axis=1)
            self.coprod_revenue = self.coprod_df['revenue'].sum()
        
        #   Update fixed cost DF
        #       If no fixed costs, set expenses to 0
        if len(self.fixed_cost_df.index) == 0:
            self.fixed_cost_df['value_per_unit'] = 0
            self.fixed_cost_expense = 0
        else:
            self.fixed_cost_df['sales'] = self.fixed_cost_df['usage'].apply(lambda x:x*sales)
            self.fixed_cost_df['value_per_unit'] = self.fixed_cost_df.apply(lambda x: x['cost']*(1.0+x['escalation'])**(analysis_year-1),axis=1)
            self.fixed_cost_expense = self.fixed_cost_df['value_per_unit'].sum() * fraction_of_year_operated
        
        #   Update capital item DF
        #       If no capital, set expenses to 0
        if len(self.capital_df.index) == 0:
            self.capital_df['capital_expenditures'] = 0
            self.capital_exp = 0
        else:
            adj_refurb_len = max(self.capital_df['refurb'].apply(lambda x:len(x)))
            self.capital_df['refurb'] = self.capital_df['refurb'].apply(lambda x: np.pad(x,pad_width=(0,adj_refurb_len-len(x))))
            self.capital_df['capital_expenditures'] = self.capital_df.apply(lambda x: np.pad(np.multiply([1.0,*x['refurb']],x['cost']),\
                                                    pad_width=(0,max(0,analysis_length-len(x['refurb'])))),axis=1)
            self.capital_exp = self.capital_df['capital_expenditures'].sum()
            self.capital_exp = self.capital_exp[0:analysis_length+1]

        #   Update incentives DF
        #       If no incentives, set revenue to 0
        if len(self.incentive_df.index) == 0:
            self.incentive_df['revenue'] = 0
            self.incentive_revenue = 0
            self.incentive_tax_credit = [0]*len(self.calendar_year)
        else:
            incentive_escalation = self.incentive_df.apply(lambda x:x['value']*(1+(-1.0*x['decay']))**(analysis_year-1),axis=1)

            bb = self.incentive_df['sunset_years'].apply(lambda x:np.logical_and(yrs_of_operation>0,yrs_of_operation<=x))
            cc = self.incentive_df['sunset_years'].apply(lambda x:np.logical_and(yrs_of_operation>x,yrs_of_operation<(x+1)))
            dd = self.vals['fraction of year operated']
            
            inc1 = incentive_escalation*bb
            inc2 = incentive_escalation*cc.apply(lambda x:x*dd*(1-np.mod(yrs_of_operation,1)))
            self.incentive_df['value_per_year'] = inc1+inc2
            self.incentive_df['revenue'] = (inc1+inc2).apply(lambda x:x*sales)

            self.incentive_revenue = self.incentive_df.loc[self.incentive_df['tax_credit']==False,'revenue'].sum()
            if (self.incentive_df['tax_credit']==True).any():
                self.incentive_tax_credit = self.incentive_df.loc[self.incentive_df['tax_credit']==True,'revenue'].sum(axis=0)
            else:  
                self.incentive_tax_credit = [0]*len(self.calendar_year)

    def clear_values(self,class_type):
        if class_type=='feedstocks':
            self.fs_df = pd.DataFrame(columns=['name','usage','unit','cost','escalation'])
        if class_type=='capital':
            self.capital_df = pd.DataFrame(columns=['name','cost','depr_type','depr_period','refurb'])
        if class_type=='incentives':
            self.incentive_df = pd.DataFrame([],columns=['name','value','decay','sunset_years'])
        if class_type=='coproducts':
            self.coprod_df = pd.DataFrame(columns=['name','usage','unit','cost','escalation'])
        if class_type=='fixed costs':
            self.fixed_cost_df = pd.DataFrame(columns=['name','usage','unit','cost','escalation'])
        if class_type=='all':
            self.fs_df = pd.DataFrame(columns=['name','usage','unit','cost','escalation'])
            self.capital_df = pd.DataFrame(columns=['name','cost','depr_type','depr_period','refurb'])
            self.incentive_df = pd.DataFrame([],columns=['name','value','decay','sunset_years','tax_credit'])
            self.coprod_df = pd.DataFrame(columns=['name','usage','unit','cost','escalation'])
            self.fixed_cost_df = pd.DataFrame(columns=['name','usage','unit','cost','escalation'])

    def plot_cashflow(self, scale='M', fileout=""):

        if scale == "M":
            scale_value = 1E-6
        elif scale == "B":
            scale_value = 1E-9
        elif scale == "":
            scale_value = 1

        plot_data = self.loan_out['investor_cash_flow']
        fig, ax = plt.subplots(figsize=(9, 4))

        bar_x = self.calendar_year
        bar_height = plot_data*scale_value
        # bar_tick_label = self.calendar_year
        # bar_label = list(np.round(plot_data, decimals=0))

        bar_plot  = plt.bar(bar_x[plot_data>=0], bar_height[plot_data>=0], color='blue')
        bar_plot2 = plt.bar(bar_x[plot_data<0], bar_height[plot_data<0], color='red')
        plt.xticks(rotation=90,labels=self.calendar_year,ticks=self.calendar_year)
        plt.ylim(top=max(bar_height)*3)

        ax.bar_label(bar_plot,rotation=90,padding=8,fmt='%i')
        ax.bar_label(bar_plot2,rotation=90,label_type='center',fmt='%i')

        ax.set(ylabel="$ (%s US)" %(scale), xlabel="Year")

        plt.subplots_adjust(left=0.05, bottom=0.2, right=0.95, top=0.9)
        # plt.ticklabel_format(useOffset=False, style='plain')
        name = 'Cash Flow'
        plt.title(name, loc='center')
        plt.tight_layout()

        if fileout != "":
            plt.savefig(fileout, transparent=True)

        plt.show()

    def plot_costs(self):

        all_flow = self.get_cost_breakdown()

        colors = all_flow.loc[:,['Name','Type']]
        colors['Color'] = ''
        color_vals = {'Operating Revenue':'#2626eb','Financing cash inflow':'#bdbdf2','Operating Expenses':'#f59342','Financing cash outflow':'#f0c099'}

        colors['Color'] = colors['Type'].map(color_vals)

        ax = all_flow.plot.barh(x='Name', y='NPV',figsize=(8,9),color=colors['Color'].values)

        plt.subplots_adjust(left=0.5, bottom=0.05, right=0.9, top=0.95)
        plt.ylabel('')
        plt.title('Real levelized value breakdown of '+self.vals['commodity']['name']+' ($/'+self.vals['commodity']['unit']+')')
        plt.xlim(right=max(all_flow['NPV'])*1.25)
       
        handles = [mpatches.Patch(color=color_vals[i]) for i in color_vals]
        labels = [f'{i}' for i in color_vals]
        plt.legend(handles, labels,loc='lower right')

        ax.bar_label(ax.containers[0],fmt='%0.2f',fontsize=6)

        plt.show()
        return all_flow

    def plot_capital_expenses(self, scale="M", fileout=""):

        if scale == "M":
            scale_value = 1E-6
        elif scale == "B":
            scale_value = 1E-9
        elif scale == "":
            scale_value = 1

        plot_df = self.capital_df
        plot_df = plot_df.rename(columns={"name": "Name"})
        series = pd.Series(plot_df["cost"].values*scale_value, index=plot_df["Name"], name="")

        ax = pd.DataFrame(series).T.plot.bar(stacked=True, legend=False)


        plt.title('Capital Expenditures by System', loc="center")

        # ax.bar_label(ax.containers[0],fmt='%0.2f',fontsize=10)

        for i in range(0, len(ax.containers)):
            c = ax.containers[i]
            # Optional: if the segment is small or 0, customize the labels
            print(c)
            print(plot_df["Name"][i])
            labels = [str(plot_df["Name"][i]) + str("\n") + str(round(v.get_height(), ndigits=2)) if v.get_height() > 0 else '' for v in c]
            
            # remove the labels parameter if it's not needed for customized labels
            ax.bar_label(c, labels=labels, label_type='center')


        ax.set(ylabel="$ (%s US)" %(scale), xlabel=None)
        plt.tight_layout()

        if fileout != "":
            plt.savefig(fileout, transparent=True)
        plt.show()

    def plot_time_series(self):
        '''
        Overview:
        ---------
            This function produces a plotly graph of all the time series data (e.g., Cumulative cash flow vs year)

        Parameters:
        -----------

        Returns:
        --------
        '''
        df = self.cash_flow_out_table

        y_vars = df.loc[:,df.columns != 'Year'].columns

        fig = go.Figure()
        first_val = True
        buttons=[]
        for y in y_vars:
            fig.add_trace(go.Bar(x=df['Year'],y=df[y],visible=first_val,marker_color=np.where(df[y]<0, 'red', 'blue')))
            first_val=False
            buttons.append(dict(method='update',
                                label=y,
                                args=[ {'visible':y_vars.isin([y])},{'y':df[y]} ]))
        updatemenu=[{'buttons':buttons,'direction':'down','showactive':True}]

        fig.update_layout(showlegend=False, updatemenus=updatemenu)

        fig.show()

    def plot_costs_yearly(self, per_kg=True, scale="M", remove_zeros=False, remove_depreciation=False, fileout=""):
        rate = self.vals['general inflation rate']
        volume = self.yearly_sales #/ (1 + rate)
        summary_vals = pd.DataFrame(self.summary_vals)
        feedstock_names = list(self.fs_df['name'].values)
        fixed_costs_names = list(self.fixed_cost_df['name'].values)
        other_names = ['Labor','Total annual maintenance','Rent of land','Property insurance','Licensing and Permitting','Interest expense','Depreciation expense']
        names = feedstock_names+fixed_costs_names + other_names

        summary_vals = summary_vals.loc[summary_vals['Name'].isin(names)]

        if scale == "M":
            scale_value = 1E-6
        elif scale == "B":
            scale_value = 1E-9
        elif scale == "":
            scale_value = 1

        for i in np.arange(len(self.calendar_year)):
            if per_kg:
                summary_vals[str(self.calendar_year[i])] = summary_vals['Amount'].apply(lambda x: x[i]/volume[i])
            else:
                summary_vals[str(self.calendar_year[i])] = summary_vals['Amount'].apply(lambda x: x[i]*scale_value)

        summary_vals = summary_vals.drop(columns=['Type','Amount'])
        summary_vals = summary_vals.set_index('Name')
        summary_vals=summary_vals.fillna(0)

        summary_vals.replace([np.inf, -np.inf], 0, inplace=True)

        summary_vals = summary_vals.T

        if remove_zeros:
            summary_vals = summary_vals.loc[:, (summary_vals != 0).any(axis=0)]

        if remove_depreciation:
            summary_vals = summary_vals.drop(columns=['Depreciation expense'])

        ax = summary_vals.plot.bar(stacked=True,figsize=(9,6))
        handles, labels = ax.get_legend_handles_labels()
        plt.legend(handles[::-1], labels[::-1],loc='best',prop={'size': 6})
        plt.title('Cost breakdown')
        plt.xlabel('Year')
        if per_kg:
            plt.ylabel('$/'+self.vals['commodity']['unit'])
        else:
            plt.ylabel('$ (%s US)' %(scale))

        if fileout != "":
            plt.savefig(fileout, transparent=True)

        plt.show()

    def plot_costs_yearly2(self, per_kg=True, scale='M', remove_zeros=False, remove_depreciation=False, fileout=""):
        rate = self.vals['general inflation rate']
        volume = self.yearly_sales #/ (1 + rate)
        summary_vals = pd.DataFrame(self.summary_vals)
        feedstock_names = list(self.fs_df['name'].values)
        fixed_costs_names = list(self.fixed_cost_df['name'].values)
        other_names = ['Labor','Total annual maintenance','Rent of land','Property insurance','Licensing and Permitting','Interest expense','Depreciation expense']
        cost_of_goods_sold = feedstock_names+fixed_costs_names + other_names

        summary_vals = summary_vals.loc[summary_vals['Name'].isin(cost_of_goods_sold)]
            
        if scale == "M":
            scale_value = 1E-6
        elif scale == "B":
            scale_value = 1E-9
        elif scale == "":
            scale_value = 1

        for i in np.arange(len(self.calendar_year)):
            if per_kg:
                summary_vals[str(self.calendar_year[i])] = summary_vals['Amount'].apply(lambda x: x[i]/volume[i])
            else:
                summary_vals[str(self.calendar_year[i])] = summary_vals['Amount'].apply(lambda x: x[i]*scale_value)

        summary_vals = summary_vals.drop(columns=['Type','Amount'])
        summary_vals = summary_vals.set_index('Name')
        summary_vals=summary_vals.fillna(0)

        summary_vals.replace([np.inf, -np.inf], 0, inplace=True)

        summary_vals = summary_vals.T
        summary_vals = summary_vals.reset_index()
        summary_vals = summary_vals.rename(columns={'index':'Year'})

        nTotal = summary_vals[cost_of_goods_sold].sum(axis=1)

        if remove_zeros:
            summary_vals = summary_vals.loc[:, (summary_vals != 0).any(axis=0)]

        if remove_depreciation:
            summary_vals = summary_vals.drop(columns=['Depreciation expense'])

        y_vars = summary_vals.loc[:,summary_vals.columns != 'Year'].columns
        
        if per_kg:
            labels = {'value':f'Nominal $/{self.vals["commodity"]["unit"]} of {self.vals["commodity"]["name"]}'}
        else:
            labels = {'value':'$ (%s US)' %(scale)}
        # print(labels)
        # quit()
        fig = px.bar(summary_vals,x='Year',y=y_vars,labels=labels,\
            color_discrete_sequence=px.colors.qualitative.Alphabet)
        # fig.add_traces(go.Scatter(x=self.calendar_year,y=self.sales_price,mode='lines'))
        # button_all = dict(label='All',method='update',args=[{'visible':y_vars.isin(y_vars),'title':'All','showlegend':True}])
        button_cogs = dict(label='Total Expenses',method='update',args=[{'visible':y_vars.isin(cost_of_goods_sold),'title':'All','showlegend':True}])
        def create_layout_button(column):
            return dict(label = column,
                    method = 'update',
                    args = [{'visible': y_vars.isin([column]),
                             'title': column,
                             'showlegend': True}])
        fig.update_layout(legend={'traceorder': 'reversed'})
        fig.update_layout(
            updatemenus=[go.layout.Updatemenu(
                active = 0,
                buttons = [button_cogs] + list(y_vars.map(lambda column: create_layout_button(column)))
                )
            ])


        if fileout != "":
            fig.write_html(fileout)

        fig.show()

        pass

    def cash_flow(self,price=None):
        #   This function calculates the NPV

        #   If no price is provided, then set to the initial value
        if price  == None:
            price = self.vals['commodity']['initial price']

        #   Set up formatted calendar years
        financial_year = self.vals['analysis start year']-1
        analysis_length = int(self.vals['operating life'] + math.ceil(self.vals['installation months']/12))
        analysis_year = np.arange(0, analysis_length+1)
        self.calendar_year = np.arange(financial_year, financial_year + analysis_length + 1)
        self.Nyears = len(self.calendar_year)
        yrs_of_operation = np.minimum(self.vals['operating life'], np.maximum(0, analysis_year - self.vals['installation months']/12))
        self.vals['fraction of year operated'] = yrs_of_operation-np.concatenate(([0], yrs_of_operation[: -1]))
        avg_utilization = np.minimum(self.vals['long term utilization']/(self.vals['demand rampup']+1)*yrs_of_operation,
                                                           self.vals['long term utilization']*np.minimum(1+(self.vals['operating life']+self.vals['installation months']/12) - analysis_year, 1))
        
        #   Yearly sales of product 
        daily_sales = self.vals['capacity']*avg_utilization
        yearly_sales = daily_sales*365
        self.yearly_sales = yearly_sales
        
        ######################################################################
        ######################################################################
        ##                               REVENUE                            ##
        ######################################################################
        ######################################################################

        def get_TOPC_revenue(TOPC,analysis_year,install_months,avg_utilization,yrs_of_operation):
            unit_price = TOPC['unit price']
            decay = TOPC['decay']
            sup_util = TOPC['support utilization']
            ss_years = TOPC['sunset years']
            TOPC_price = unit_price*(1.0-decay)**(analysis_year)
            shift = math.ceil(max(install_months/12, 1))
            TOPC_price = np.concatenate((np.zeros(shift), TOPC_price[:-shift]))
            TOPC_volume = np.maximum(sup_util-avg_utilization,0)\
                            *self.vals['capacity']*365*(yrs_of_operation>0)*(yrs_of_operation<=ss_years)
            TOPC_revenue = TOPC_price * TOPC_volume
            return TOPC_revenue,TOPC_volume

        def incentive_revenue(incentive,yoo):
            a = incentive['value']
            #   This will only apply to annual operating expense
            if 'sunset years' in incentive:
                b = incentive['decay'] # This is linear decay
                c = incentive['sunset years']
                aa = ((a-(a*b)*(np.floor(yoo)-1))*(1-(yoo%1)))
                bb = ((a-(a*b)*(np.floor(yoo)  ))*(   yoo%1 ))
                aa[np.invert((np.floor(yoo)>0) & ( np.floor(yoo)   <=c))] = 0
                bb[np.invert((np.floor(yoo)>-1) & ((np.floor(yoo)+1)<=c))] = 0
            #   This will only apply to incidental revenue
            else:   
                b = incentive['escalation']
                aa = ((a*(1+b)** (np.floor(yoo)-1))*(1 - (yoo % 1)))
                bb = ((a*(1+b)** (np.floor(yoo)  ))*     (yoo % 1) )
                aa[np.invert(np.floor(yoo)>0)] = 0
                bb[np.invert(np.floor(yoo)>-1)] = 0
            return aa+bb

        def escalate(value,rate,analysis_year):
            return value*(1.0+rate)**(analysis_year-1)

        #   Revenue from sale of product
        sales_price = price*(1.0+self.vals['commodity']['escalation'])**(analysis_year-1)
        sales_revenue = sales_price * yearly_sales

        # Updates feedstock, fixed cost, incentive, coproduct, and capital dataframes
        self.update_sales(analysis_length,yrs_of_operation)

        #   Take or pay contract revenue
        TOPC_revenue,TOPC_volume = get_TOPC_revenue(self.vals['TOPC'],analysis_year,self.vals['installation months'],avg_utilization,yrs_of_operation)
        
        # Annual operating incentive revenue
        annul_op_incent_rev = incentive_revenue(self.vals['annual operating incentive'],yrs_of_operation)

        #   Incidental revenue
        incidental_rev = incentive_revenue(self.vals['incidental revenue'],yrs_of_operation)

        #   Road tax, credit card fees, sales tax
        credit_card_fees_array = -self.vals['credit card fees']*sales_revenue
        sales_taxes_array = -self.vals['sales tax']*sales_revenue
        road_taxes = -escalate(self.vals['road tax']['value'],self.vals['road tax']['escalation'],analysis_year)*yearly_sales

        #   Total revenue is sum of revenue streams minus fees and taxes
        total_revenue = sales_revenue \
                            +self.coprod_revenue \
                            +annul_op_incent_rev \
                            +self.incentive_revenue \
                            +TOPC_revenue\
                            +incidental_rev\
                            +credit_card_fees_array\
                            +sales_taxes_array\
                            +road_taxes

        

        ######################################################################
        ######################################################################
        ##                      Operating Expenses                          ##
        ######################################################################
        ######################################################################

        # Labor, maintenance, rent of land, license and permit rate escalation and expense calculation
        labor_rate = escalate(self.vals['labor']['rate'],self.vals['labor']['escalation'],analysis_year)
        maintenance = escalate(self.vals['maintenance']['value'],self.vals['maintenance']['escalation'],analysis_year)
        rent_of_land = escalate(self.vals['rent']['value'],self.vals['rent']['escalation'],analysis_year)
        license_and_permit = escalate(self.vals['license and permit']['value'],self.vals['license and permit']['escalation'],analysis_year)
        labor_expense = self.vals['fraction of year operated']*labor_rate*self.vals['labor']['value']
        maintenance_expense = self.vals['fraction of year operated']*maintenance
        rent_expense = self.vals['fraction of year operated']*rent_of_land
        license_and_permit_expense = self.vals['fraction of year operated']*license_and_permit

        #   One time incetive at project start
        receipt_one_time_cap_incentive = np.pad([self.vals['one time cap inct']['value']], pad_width=(0,analysis_length))

        #   Non depreciable assets expenditure at project start
        non_depr_assets_exp = np.pad([self.vals['non depr assets']], pad_width=(0, analysis_length))

        #   Installation cost expenditure at project start
        installation_expenditure = np.pad([self.vals['installation cost']['value']], pad_width=(0, analysis_length))

        #   Net cash by investing (sum of capital expenses, non depreciable assets, and installation)
        net_cash_by_investing = -1*(self.capital_exp+non_depr_assets_exp+installation_expenditure)
        all_plant_prop_and_equip = np.cumsum(-1*net_cash_by_investing)

                    ######################################################################
                    ##                            Depreciating                          ##
                    ######################################################################

        #   Depreciate capital costs
        #   if no capital items, set to zero
        self.capital_df[['refurb_depr_schedule','depr_schedule']] = self.capital_df.apply(lambda x: self.depreciate(x['depr_type'],x['depr_period'],x['refurb'],x['cost']),axis=1,result_type='expand') \
                                if len(self.capital_df.index)!=0 else 0
        max_cap_years = self.capital_df[['refurb_depr_schedule','depr_schedule']].apply(lambda x: max(len(x['refurb_depr_schedule']),len(x['depr_schedule'])),axis=1).iat[0] \
                                if len(self.capital_df.index)!=0 else 0

        #   Depreciate installation and one time capital incentive
        #   TODO: check this. One is ==yes one is ==no
        (_,installation_depr_sch)=self.depreciate(self.vals['installation cost']['depr type'],self.vals['installation cost']['depr period'],[0],self.vals['installation cost']['value']*self.vals['installation cost']['depreciable'])
        (_,cap_inct_depr_sch)=self.depreciate(self.vals['one time cap inct']['depr type'],self.vals['one time cap inct']['depr period'],[0],-1*self.vals['one time cap inct']['value']*(not self.vals['one time cap inct']['depreciable']))

        #   Depreciation and refurb years, can vary. Set all to the same total time
        max_depr_years = max(max_cap_years,len(installation_depr_sch),len(cap_inct_depr_sch))

        # Pad depreciation schedules to be the same length
        self.capital_df['refurb_depr_schedule'] = self.capital_df['refurb_depr_schedule'].apply(lambda x:np.pad(x,pad_width=(0,max_depr_years-len(x))))
        self.capital_df['depr_schedule'] = self.capital_df['depr_schedule'].apply(lambda x:np.pad(x,pad_width=(0,max_depr_years-len(x))))
        installation_depr_sch = np.pad(installation_depr_sch,pad_width=(0,max_depr_years-len(installation_depr_sch)))
        cap_inct_depr_sch = np.pad(cap_inct_depr_sch,pad_width=(0,max_depr_years-len(cap_inct_depr_sch)))

        #   Depreciation schedules
        all_depr = self.capital_df['depr_schedule'].sum() + self.capital_df['refurb_depr_schedule'].sum() + installation_depr_sch + cap_inct_depr_sch
        cum_depr = np.cumsum(all_depr)

        #   Cumulative depreciable capital
        self.capital_df['cum_depr_cap'] = self.capital_df.apply(lambda x: np.multiply(x['cost'],x['refurb'])+[x['cost'],*np.zeros(len(x['refurb'])-1)] ,axis=1) if len(self.capital_df.index)!=0 else 0
        cum_depr_cap = self.capital_df['cum_depr_cap'].sum() if len(self.capital_df.index)!=0 else [0]
        install_depr_cap = np.multiply([self.vals['installation cost']['value'],*np.zeros(len(cum_depr_cap)-1) ] , self.vals['installation cost']['depreciable'])
        one_time_inct_depr_cap = np.multiply([self.vals['one time cap inct']['value'],*np.zeros(len(cum_depr_cap)-1) ] , not self.vals['one time cap inct']['depreciable'])
        cum_depr_cap += install_depr_cap - one_time_inct_depr_cap     
        cum_depr_cap = np.concatenate((np.cumsum(cum_depr_cap),np.ones(len(cum_depr)-len(cum_depr_cap))*np.cumsum(cum_depr_cap)[-1]))
        
        un_depr_cap = cum_depr_cap-cum_depr
        cum_PPE = np.cumsum(-net_cash_by_investing)
        cum_depr = np.multiply(-1,[0,*cum_depr][:self.Nyears])

        #   Total plant property equipment
        net_ppe = cum_PPE+cum_depr
        property_insurance = self.vals['fraction of year operated'] * net_ppe * self.vals['property tax and insurance percent']
        admin_expense = (sales_revenue+self.coprod_revenue)*self.vals['admin expense percent']

        #   All operating expenses
        total_operating_expenses = self.fs_expense \
                                    +labor_expense\
                                    +rent_expense\
                                    +property_insurance\
                                    +license_and_permit_expense\
                                    +admin_expense    \
                                    +maintenance_expense\
                                    +self.fixed_cost_expense

        #   Earning before tax depreciation
        earnings_before_int_tax_depr = total_revenue - total_operating_expenses

        ######################################################################
        ######################################################################
        ##                              LOAN                          ##
        ######################################################################
        ######################################################################
        NPV = self.loan_calc(un_depr_cap,net_cash_by_investing,receipt_one_time_cap_incentive,all_depr,earnings_before_int_tax_depr,annul_op_incent_rev,total_revenue,total_operating_expenses,net_ppe)


        ######################################################################
        ######################################################################
        ##                          Summary Values                          ##
        ######################################################################
        ######################################################################
        self.summary_vals={'Type':[],'Name':[],'Amount':[]}
        #   Add operating revenue
        names = [f'{self.vals["commodity"]["name"]} sales','Take or pay revenue','Incidental revenue','Sale of non-depreciable assets','Cash on hand recovery']
        names.extend(self.coprod_df['name'].values)
        amount = [sales_revenue,TOPC_revenue,incidental_rev,self.loan_out['sale_of_non_depreciable_assets'],np.minimum(self.loan_out['net_change_cash_equiv'],0)]
        amount.extend(self.coprod_df['revenue'].values)
        self.summary_vals['Name'].extend(names)
        self.summary_vals['Type'].extend(['Operating Revenue']*len(names))
        self.summary_vals['Amount'].extend(amount)
       
        #   Add operating expenses
        names = ['Property insurance','Road tax','Credit card fees','Sales tax','Installation cost','Total annual maintenance','Cash on hand reserve','Non-depreciable assets','Labor','Administrative expenses','Rent of land','Licensing and Permitting']
        names.extend(self.capital_df['name'].values)
        names.extend(self.fixed_cost_df['name'].values)
        names.extend(self.fs_df['name'].values)
        amount = [property_insurance,road_taxes,credit_card_fees_array,sales_taxes_array,installation_expenditure,maintenance_expense,np.maximum(self.loan_out['net_change_cash_equiv'],0),non_depr_assets_exp,labor_expense,admin_expense,rent_expense,license_and_permit_expense]
        amount.extend(self.capital_df['capital_expenditures'].values)
        amount.extend(self.fixed_cost_df['value_per_unit'].apply(lambda x:x*self.vals['fraction of year operated']))
        amount.extend(self.fs_df['expense'].values)
        self.summary_vals['Name'].extend(names)
        self.summary_vals['Type'].extend(['Operating Expenses']*len(names))
        self.summary_vals['Amount'].extend(amount)

        #   Add financing cash inflow
        names = ['Inflow of equity','Inflow of debt','Monetized tax losses','One time capital incentive','Annual operating incentives']
        names.extend(self.incentive_df.loc[self.incentive_df['tax_credit']==False,'name'].values)
        amount = [self.loan_out['inflow_of_equity'],self.loan_out['inflow_of_debt'],self.loan_out['monetized_tax_losses'],receipt_one_time_cap_incentive,annul_op_incent_rev]
        amount.extend(self.incentive_df.loc[self.incentive_df['tax_credit']==False,'revenue'].values)
        self.summary_vals['Name'].extend(names)
        self.summary_vals['Type'].extend(['Financing cash inflow']*len(names))
        self.summary_vals['Amount'].extend(amount)

        #   Add financing cash outflow
        names = ['Dividends paid','Income taxes payable','Repayment of debt','Interest expense','Capital gains taxes payable']
        amount = [self.loan_out['dividends_paid'],np.maximum(self.loan_out['income_taxes_payable'],0),self.loan_out['repayment_of_debt'],self.loan_out['interest_pmt'],self.loan_out['capital_gains_taxes_payable']]
        self.summary_vals['Name'].extend(names)
        self.summary_vals['Type'].extend(['Financing cash outflow']*len(names))
        self.summary_vals['Amount'].extend(amount)

        self.summary_vals['Name'].append('Depreciation expense')
        self.summary_vals['Type'].append(' NA')
        self.summary_vals['Amount'].append(self.loan_out['depreciation_expense'])

        ###########
        #   Organize cash flow table
        ########### 
        comod_unit = self.vals["commodity"]["unit"]
        comod_name = self.vals["commodity"]["name"]
        all_depr_crop = np.concatenate(([0],all_depr[0:len(self.calendar_year)-1]))
        cash_flow_out = {'Year':self.calendar_year,
                                            'Cumulative cash flow':np.cumsum(self.loan_out['investor_cash_flow']),
                                            'Investor cash flow':self.loan_out['investor_cash_flow'],
                                            'Monetized tax losses':-1*np.minimum(self.loan_out['income_taxes_payable'],0),
                                            'Gross margin': np.divide((total_revenue-total_operating_expenses),total_revenue,out=np.zeros_like(total_revenue),where=total_revenue!=0),
                                            'Cost of goods sold ($/year)':total_operating_expenses-admin_expense+all_depr_crop+self.loan_out['interest_pmt'],
                                            f'Cost of goods sold ($/{comod_unit})':np.divide(total_operating_expenses-admin_expense+all_depr_crop+self.loan_out['interest_pmt'],yearly_sales,out=np.zeros_like(yearly_sales),where=yearly_sales>0),
                                            'Average utilization':avg_utilization,
                                            f'{comod_name} sales ({comod_unit}/day)':daily_sales,
                                            f'Capacity covered by TOPC ({comod_unit}/day)':TOPC_volume/365,
                                            f'Cost of {comod_name} ($/{comod_unit})':sales_price,
                                            f'{comod_name} sales ({comod_unit}/year)':yearly_sales}
        for index,coprod in self.coprod_df.iterrows():
            cash_flow_out[f"Value of {coprod['name']} ($/{coprod['unit']})"] = coprod['value_per_unit']
            cash_flow_out[f"{coprod['name']} sales ($/year)"] = coprod['revenue']
        for index,fs in self.fs_df.iterrows():
            cash_flow_out[f"Value of {fs['name']} ($/{fs['unit']})"] = fs['value_per_unit']
            cash_flow_out[f"{fs['name']} expenses ($/year)"] = fs['expense']
        for index,inct in self.incentive_df.iterrows():
            cash_flow_out[f"Value of {inct['name']} ($/{comod_unit})"] = inct['value_per_year']
            cash_flow_out[f"{inct['name']} ($/year)"] = inct['revenue']    
        cash_flow_out.update({'Annual operating incentive ($/year)':annul_op_incent_rev,
                            'Incidental revenue ($/year)':incidental_rev,
                            'Credit card fees ($/year)':credit_card_fees_array,
                            'Sales tax ($/year)':sales_taxes_array,
                            'Road tax ($/year)':road_taxes,
                            'Total revenue ($/year)':total_revenue,
                            'Total feedstock/utilities cost ($/year)':self.fs_expense,
                            'Labor ($/year)':labor_expense,
                            'Total annual maintenance ($/year)':maintenance_expense,
                            'Rent of land ($/year)':rent_expense,
                            'Property insurance ($/year)':property_insurance,
                            'Licensing & permitting ($/year)':license_and_permit_expense,
                            'Administrative expense ($/year)':admin_expense})
        for index,fixed_cost in self.fixed_cost_df.iterrows():
            cash_flow_out[f"{fixed_cost['name']} expenses ({fixed_cost['unit']})"] = fixed_cost['value_per_unit']
        cash_flow_out.update({'Total operating expense ($/year)':total_operating_expenses,
                            'EBITD ($/year)':earnings_before_int_tax_depr,
                            'Interest on outstanding debt ($/year)':self.loan_out['interest_pmt'],
                            'Depreciation ($/year)':all_depr_crop,
                            'Taxable income ($/year)':self.loan_out['taxable_income'],
                            'Remaining available deferred carry-forward tax losses ($/year)':0,#COME BACK TO THIS
                            'Income taxes payable ($/year)':self.loan_out['income_taxes_payable'],
                            'Income before extraordinary items ($/year)':self.loan_out['income_before_extraordinary_items'],
                            'Sale of non-depreciable assets ($/year)':self.loan_out['sale_of_non_depreciable_assets'],
                            'Net capital gains or loss ($/year)':self.loan_out['sale_of_non_depreciable_assets']-non_depr_assets_exp,
                            'Capital gains taxes payable ($/year)':self.loan_out['capital_gains_taxes_payable'],
                            'Net income ($/year)':self.loan_out['net_income'],
                            'Net annual operating cash flow ($/year)':self.loan_out['net_income']+all_depr_crop})
        for index,capital in self.capital_df.iterrows():
            cash_flow_out[f"Capital expenditure for {capital['name']} ($/year)"] = capital['capital_expenditures'][0:len(self.calendar_year)]
        cash_flow_out.update({'Expenditure for non-depreciable fixed assets ($/year)':-non_depr_assets_exp,
                            'Capital expenditures for equipment installation ($/year)':installation_expenditure,
                            'Total capital expenditures ($/year)':-net_cash_by_investing,
                            'Incurrence of debt ($/year)':self.loan_out['inflow_of_debt'],
                            'Repayment of debt ($/year)':self.loan_out['repayment_of_debt'],
                            'Inflow of equity ($/year)':self.loan_out['inflow_of_equity'],
                            'Dividends paid ($/year)':self.loan_out['dividends_paid'],
                            'One-time capital incentive ($/year)':receipt_one_time_cap_incentive,
                            'Net cash for financing activities ($/year)':self.loan_out['inflow_of_debt']+self.loan_out['repayment_of_debt']+self.loan_out['inflow_of_equity']+self.loan_out['dividends_paid']+annul_op_incent_rev,
                            'Net change of cash ($/year)':self.loan_out['net_change_cash_equiv'],
                            'Cumulative cash ($/year)':self.loan_out['cumulative_cash'],
                            'Cumulative PP&E ($/year)':all_plant_prop_and_equip,
                            'Cumulative depreciation ($/year)':cum_depr,
                            'Net PP&E ($/year)':net_ppe,
                            'Cumulative deferred tax losses ($/year)':self.loan_out['cumulative_deferred_tax_losses'],
                            'Total assets ($/year)':self.loan_out['total_assets'],
                            'Cumulative debt ($/year)':self.loan_out['cumulative_debt'],
                            'Total liabilities ($/year)':self.loan_out['cumulative_debt'],
                            'Cumulative capital incentives equity ($/year)':self.loan_out['cumulative_equity_from_capital_incentives'],
                            'Cumulative investor equity ($/year)':self.loan_out['cumulative_equity_investor_contribution'],
                            'Retained earnings ($/year)':self.loan_out['retained_earnings'],
                            'Total equity ($/year)':self.loan_out['total_equity'],
                            'Investor equity less capital incentive ($/year)':self.loan_out['total_equity']-self.loan_out['cumulative_equity_from_capital_incentives'],
                            'Returns on investor equity':np.divide(self.loan_out['net_income'],self.loan_out['total_equity']-self.loan_out['cumulative_equity_from_capital_incentives'],out=np.zeros_like(self.loan_out['net_income']),where=self.loan_out['total_equity']-self.loan_out['cumulative_equity_from_capital_incentives']!=0),
                            'Debt/Equity ratio':np.divide(self.loan_out['cumulative_debt'],self.loan_out['total_equity'],out=np.zeros_like(self.loan_out['total_equity']),where=self.loan_out['total_equity']!=0),
                            'Returns on total equity':np.divide(self.loan_out['net_income'],self.loan_out['total_equity'],out=np.zeros_like(self.loan_out['total_equity']),where=self.loan_out['total_equity']!=0),
                            'Debt service coverage ratio (DSCR)':np.divide((total_revenue-cash_flow_out['Cost of goods sold ($/year)']),total_revenue,out=np.zeros_like(total_revenue),where=total_revenue>0)})
        
        self.cash_flow_out_table = pd.DataFrame(cash_flow_out)

        self.irr = npf.irr(self.loan_out['investor_cash_flow'])
        self.profit_index = -1*npf.npv(self.vals['general inflation rate'],[0,*self.loan_out['investor_cash_flow'][1:]])/self.loan_out['investor_cash_flow'][0]
        self.cum_cash_flow = cash_flow_out['Cumulative cash flow']
        self.LCO = npf.npv(self.vals['general inflation rate'],sales_revenue/(sum(self.yearly_sales) / (1 + self.vals['general inflation rate'])))
        positive_flow = np.where(self.cum_cash_flow>0)[0]
        positive_EBITD = np.where(earnings_before_int_tax_depr>0)[0]
        if(len(positive_flow)>0):
            self.first_year_positive = positive_flow[0] 
        else:
            self.first_year_positive= -1
        if(len(positive_EBITD)>0):
            self.first_year_positive_EBITD = positive_EBITD[0] 
        else:
            self.first_year_positive_EBITD= -1

        
        return NPV

    def solve_price(self):
        t1 = time.time()
        iters = 15
        gain = 0.95
        P = np.zeros(iters)
        P[0] = 1
        P[1] = 2
        NPV = np.zeros(iters)
        price = P[0]
        NPV[0] = self.cash_flow(price)
        for i in range(1, iters - 1):
            price = P[i]
            NPV[i] = self.cash_flow(price)
            if abs(NPV[i])<0.0001:
                break
            coefs = np.polyfit(P[i - 1:i + 1], NPV[i - 1:i + 1], 1)
            P[i + 1] = P[i]*(1-gain)+(-coefs[1] / coefs[0])*gain

        timing = time.time()-t1
        return_vals = {'NPV':NPV[i],'price':price,'irr':self.irr,'profit index':self.profit_index,\
            'first year positive':self.first_year_positive,'first year positive EBITD':self.first_year_positive_EBITD,\
                'timing':timing,'lco':self.LCO}

        return return_vals
    
    def loan_calc(self,un_depr_cap,net_cash_by_investing,receipt_one_time_cap_incentive,all_depr,earnings_before_int_tax_depr,annul_op_incent_rev,total_revenue,total_operating_expenses,net_ppe):
        #   Pre-allocate lots of lists with zeros
        inflow_of_debt,repayment_of_debt,inflow_of_equity,dividends_paid,interest_pmt,cumulative_debt,taxable_income\
            ,net_income,net_cash,cumulative_cash,cumulative_tax_loss_carryforward,net_cash_in_financing,net_change_cash_equiv\
            ,income_taxes_payable,income_before_extraordinary_items,sale_of_non_depreciable_assets,less_initial_cost\
                 = (np.zeros(self.Nyears) for i in range(17))
        dt = self.vals['tax loss carry forward years']
        deferments = np.zeros((dt+1,self.Nyears+1))
        loan_repayments   = np.zeros([self.Nyears, self.Nyears+self.vals['loan period if used']])
        loan_interest     = np.zeros([self.Nyears, self.Nyears+self.vals['loan period if used']])

        #   These occur at the end of the project
        sale_of_non_depreciable_assets[-1] = self.vals['end of proj sale non depr assets']
        less_initial_cost[-1] = -1*self.vals['non depr assets']

        #   Change in depreciable assets
        net_gain_or_loss_sale_non_depreciable_assets = sale_of_non_depreciable_assets + less_initial_cost
        capital_gains_taxes_payable = net_gain_or_loss_sale_non_depreciable_assets * self.vals['capital gains tax rate']
        if not self.vals['tax losses monetized']:
            capital_gains_taxes_payable = np.maximum(capital_gains_taxes_payable,0)

        #   Sale of undepreciated capital - occurs at end of proj
        sale_residual_undepreciated_assets = np.zeros(self.Nyears)
        loss_residual_undepreciated_assets = np.zeros(self.Nyears)
        sale_residual_undepreciated_assets[-1] =   un_depr_cap[self.Nyears-2]*(self.vals['sell undepreciated cap'])
        loss_residual_undepreciated_assets[-1] = - un_depr_cap[self.Nyears-2]*(not self.vals['sell undepreciated cap'])

        #   Extraordinary items after tax
        extraordinary_items_after_tax = sale_of_non_depreciable_assets - capital_gains_taxes_payable + sale_residual_undepreciated_assets + loss_residual_undepreciated_assets
        
        #   Inflow of equity and debt
        inflow_of_equity[0] =- (net_cash_by_investing[0] + receipt_one_time_cap_incentive[0]) / (1 + self.vals['debt equity ratio of initial financing'])
        inflow_of_debt[0] = - net_cash_by_investing[0] - inflow_of_equity[0] - receipt_one_time_cap_incentive[0]

        ########################## INITIATION OF LOAN CALCS
        if self.vals['debt type'] == "One time loan":
            loan_period = self.vals['loan period if used']
            rate = self.vals['debt interest rate'] / 12
            per = np.arange(1,12*loan_period+1).reshape(loan_period,12)
            nper = loan_period*12
            pv = inflow_of_debt[0]

            loan_repayments[0,1:(loan_period+1)] = npf.ppmt(rate,per,nper,pv).sum(axis=1)
            loan_interest[0,1:(loan_period+1)]   = npf.ipmt(rate,per,nper,pv).sum(axis=1)
        ##########################
        depreciation_expense = np.concatenate(([0],all_depr))
        cumulative_debt[0] = inflow_of_debt[0]
        net_cash_in_financing[0] = inflow_of_debt[0]+inflow_of_equity[0]+self.vals['one time cap inct']['value']

        # TODO vectorize?
        for i in range(0,self.Nyears):
            # Interest payment depending on debt type
            if self.vals['debt type'] == "Revolving debt":
                interest_pmt[i] = self.vals['debt interest rate']*cumulative_debt[i-1]*(1-(self.Nyears==(i+1))*(1-self.vals['fraction of year operated'][i]))
            elif self.vals['debt type'] == "One time loan":
                interest_pmt[i] = - loan_interest.sum(axis=0)[i]
        
            # Taxable income
            taxable_income[i]  = earnings_before_int_tax_depr[i]- interest_pmt[i]- depreciation_expense[i]\
                                    - (not self.vals['operating incentives taxable'])* (annul_op_incent_rev[i])
            #   Deferments calculations
            deferments[0,i] = taxable_income[i]*self.vals['total income tax rate']-self.incentive_tax_credit[i]
            ND = len(deferments)
            y = np.flip(np.arange(1,ND))
            for Y in range(1, ND):
                if (deferments[y[Y-1], 0] < (dt + 1)):
                    if (sum(deferments[(y[Y-1] + 1):(1 + dt), i]) == 0):
                        deferments[y[Y-1], i] = min(sum(deferments[y[Y-1]:dt, i - 1]) \
                                + min(deferments[y[Y-1] - 1, i - 1], 0) + max(deferments[0, i], 0), 0)
                    else:
                        deferments[y[Y-1], i] = min(deferments[y[Y-1] - 1, i - 1], 0)
                if (deferments[0, i] == dt):
                    deferments[y[Y-1], i] = deferments[y[Y-1], i] + min(deferments[y[Y-1] - 1, i - 1] + max(deferments[0, i], 0), 0)

            #   Set income taxes payable depending on if tax losses are monetized
            if not self.vals['tax losses monetized']:
                if dt > 0:
                    income_taxes_payable[i] = float(max(0,max(0, deferments[0, i ])+ sum(np.minimum(0, deferments[0:dt, i-1]))))
                else:
                    income_taxes_payable[i] = np.maximum(deferments[0, 1:], np.zeros(self.Nyears))
            else:
                income_taxes_payable[i] = deferments[0, i]
            
            #   Income before extraordinary items
            income_before_extraordinary_items[i] = total_revenue[i]-total_operating_expenses[i]-interest_pmt[i]-depreciation_expense[i]-income_taxes_payable[i]

            #   Net income and cash
            net_income[i] = income_before_extraordinary_items[i] + extraordinary_items_after_tax[i]
            net_cash[i] = net_income[i] + depreciation_expense[i]
            #   Cumulative cash
            cumulative_cash[i] = (total_operating_expenses[i]+interest_pmt[i]+income_taxes_payable[i])/12*(i<(self.Nyears-1))*self.vals['cash onhand percent']
            #   Net cash
            net_change_cash_equiv[i] = cumulative_cash[i] - cumulative_cash[i-1]
            net_cash_in_financing[i] = net_change_cash_equiv[i] - net_cash_by_investing[i] - net_cash[i]

            #  Repayment of debt based on debt type
            if i == (self.Nyears-1):
                repayment_of_debt[i] = -cumulative_debt[-2]
            elif self.vals['debt type'] == "One time loan":
                repayment_of_debt[i]= loan_repayments.sum(axis=0)[i]

            if (i>0) and (net_cash_by_investing[i]<0) :
                inflow_of_debt[i] = max(net_cash_in_financing[i]-repayment_of_debt[i]-receipt_one_time_cap_incentive[i],0)\
                                            /(1+self.vals['debt equity ratio of initial financing'])*self.vals['debt equity ratio of initial financing']

            #Setting up loan payment and interest for debt financed refurbishments
            if self.vals['debt type'] == "One time loan":
                loan_period = self.vals['loan period if used']
                rate = self.vals['debt interest rate'] / 12
                per = np.arange(1,12*loan_period+1).reshape(loan_period,12)
                nper = loan_period*12
                pv = inflow_of_debt[i]
                loan_repayments[i, i+1:(loan_period+i+1)] = npf.ppmt(rate,per,nper,pv).sum(axis=1)
                loan_interest[i, i+1:(loan_period+i+1)]   = npf.ipmt(rate,per,nper,pv).sum(axis=1)
            #######################################################################
            if i>0:
                inflow_of_equity[i] = max(net_cash_in_financing[i]- repayment_of_debt[i]-receipt_one_time_cap_incentive[i],0)
                if net_cash_by_investing[i]!=0: 
                    inflow_of_equity[i] = inflow_of_equity[i] / (1 + self.vals['debt equity ratio of initial financing'])

            cumulative_debt[i] = cumulative_debt[i-1]+inflow_of_debt[i]+repayment_of_debt[i]

        dividends_paid = np.clip(net_cash_in_financing-inflow_of_debt-repayment_of_debt-receipt_one_time_cap_incentive,a_min=None,a_max=0)
        dividends_paid[0] = 0

        total_liabilities = cumulative_debt
        cumulative_tax_loss_carryforward = np.concatenate(([0],-deferments[1:dt+1, 1:].sum(axis=0)))[:self.Nyears]

        total_assets = net_ppe+cumulative_cash+cumulative_tax_loss_carryforward

        cumulative_equity_from_capital_incentives = np.cumsum(receipt_one_time_cap_incentive)
        cumulative_equity_investor_contribution = np.cumsum(inflow_of_equity)
        retained_earnings = np.cumsum(net_income) + np.cumsum(dividends_paid)
        cumulative_deferred_tax_losses = cumulative_tax_loss_carryforward

        total_equity = cumulative_equity_from_capital_incentives+cumulative_equity_investor_contribution+retained_earnings+cumulative_deferred_tax_losses

        #Assets - liabilities - equity check
        AmLmEcheck = total_assets - total_equity - total_liabilities

        #investor cash flow
        investor_cash_flow = -(inflow_of_equity+dividends_paid)

        # NPV = npf.npv(self.vals['general inflation rate'], investor_cash_flow)

        NPV = npf.npv(self.vals['leverage after tax nominal discount rate'], investor_cash_flow)
        # print(NPV)

        monetized_tax_losses = np.minimum(income_taxes_payable,0)-np.minimum(capital_gains_taxes_payable,0)
        self.loan_out = {'sale_of_non_depreciable_assets':sale_of_non_depreciable_assets,'net_change_cash_equiv':net_change_cash_equiv,
                'inflow_of_equity':inflow_of_equity,'inflow_of_debt':inflow_of_debt,'dividends_paid':dividends_paid,
                'income_taxes_payable':income_taxes_payable,'repayment_of_debt':repayment_of_debt,'interest_pmt':interest_pmt,
                'capital_gains_taxes_payable':capital_gains_taxes_payable,'monetized_tax_losses':monetized_tax_losses,
                'depreciation_expense':depreciation_expense,'taxable_income':taxable_income,
                'income_before_extraordinary_items':income_before_extraordinary_items,'net_income':net_income,
                'cumulative_cash':cumulative_cash,'cumulative_deferred_tax_losses':cumulative_deferred_tax_losses,
                'total_assets':total_assets,'cumulative_debt':cumulative_debt,
                'cumulative_equity_from_capital_incentives':cumulative_equity_from_capital_incentives,
                'cumulative_equity_investor_contribution':cumulative_equity_investor_contribution,
                'retained_earnings':retained_earnings,'total_equity':total_equity,'investor_cash_flow':investor_cash_flow}

        return NPV

    def depreciate(self,type,period,percent,cap):
        #   Parameters for MACRS depreciation table (quarterly)
        ypis = np.ceil((self.vals['installation months']+1)/12)
        qpis = np.ceil(((self.vals['installation months']+0.5)/12 - np.floor((self.vals['installation months']+0.5)/12))*4)
        if type == 'MACRS':
            col = f'Q{int(qpis)}_{period}'
            depr_table = self.MACRS_table[col].values
            equip_depr_sch_pct = np.concatenate((np.zeros(int(ypis)-1), depr_table))
        elif type == 'Straight line':
            equip_depr_sch_pct = np.diff(np.minimum(np.cumsum(self.vals['fraction of year operated']/period),1))
        
        equip_depr_schedule = equip_depr_sch_pct * cap

        A = percent
        B = equip_depr_schedule[equip_depr_schedule != 0]

        lenA = len(A)
        lenB = len(B)

        # if lenA>lenB:
        #     B = np.pad(B, (0, lenA-lenB), 'constant')
        # elif lenB>lenA:
        #     A = np.pad(A,(0,lenB-lenA), 'constant')

        # B = np.pad(B, (0, max(lenA, lenB)), 'constant')
        # A = np.pad(A, (0, max(lenB, lenA)), 'constant')
        # print(A,np.flip(B))
        C,D = np.meshgrid(A,np.flip(B))
        E = (C*D).transpose()
        
        maxlen = max(lenA,lenB)

        # depr_charge = []
        # for i in range(0,asdfa+20-4):
        #     depr_charge.append(np.trace(E,offset=i-20+7))
        # print(depr_charge)

        rows,cols = E.shape
        rows_arr = np.arange(rows)
        cols_arr = np.arange(cols)
        diag_idx = rows_arr[:,None] - (cols_arr - (cols-1))
        depr_charge = np.bincount(diag_idx.ravel(),weights= E.ravel())
        depr_sum = sum(depr_charge)
        depr_charge = np.pad(depr_charge,(0,maxlen*2-len(depr_charge)))
        return depr_charge,equip_depr_schedule

    def get_cost_breakdown(self):
        rate = self.vals['general inflation rate']
        volume = sum(self.yearly_sales) / (1 + rate)
        summary_vals = pd.DataFrame(self.summary_vals)
        summary_vals = summary_vals.loc[summary_vals['Type'].isin(['Operating Revenue','Financing cash inflow','Operating Expenses','Financing cash outflow'])]
        summary_vals['NPV'] = summary_vals['Amount'].apply(lambda x:abs(npf.npv(rate,x/volume)))
        summary_vals = summary_vals.sort_values(by=['Type','NPV'],ascending=False)

        inflow = summary_vals.loc[summary_vals['Type'].isin(['Operating Revenue','Financing cash inflow'])].sort_values('NPV',ascending=True)
        outflow = summary_vals.loc[summary_vals['Type'].isin(['Operating Expenses','Financing cash outflow'])].sort_values('NPV',ascending=True)
        all_flow = pd.concat([outflow,inflow]).reset_index()
        # all_flow = all_flow.loc[all_flow['NPV']!=0]

        return all_flow