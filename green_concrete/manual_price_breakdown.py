def manual_price_breakdown(
        self, 
        gen_inflation, 
        price_breakdown
    ):
    '''
    Exports a spreadsheet-ready dictionary needed for capatability with HOPP

    Holds essentially the same information as ProFAST's price breakdown
    '''  

    price_breakdown_capex = dict()  
    price_breakdown_feed = dict()
    
    # CAPEX
    for key in self.equip_costs.keys():
        price_breakdown_capex[key] = price_breakdown.loc[price_breakdown['Name']==key,'NPV'].tolist()[0]

    price_breakdown_installation = price_breakdown.loc[price_breakdown['Name']=='Installation cost','NPV'].tolist()[0]

    # fixed OPEX
    price_breakdown_labor_cost_annual = price_breakdown.loc[price_breakdown['Name']=='Annual Operating Labor Cost','NPV'].tolist()[0]  
    price_breakdown_labor_cost_maintenance = price_breakdown.loc[price_breakdown['Name']=='Maintenance Labor Cost','NPV'].tolist()[0]  
    price_breakdown_labor_cost_admin_support = price_breakdown.loc[price_breakdown['Name']=='Administrative & Support Labor Cost','NPV'].tolist()[0] 
    
    # variable OPEX
    price_breakdown_maintenance_materials = price_breakdown.loc[price_breakdown['Name']=='Maintenance Materials','NPV'].tolist()[0]  
    price_breakdown_taxes = price_breakdown.loc[price_breakdown['Name']=='Income taxes payable','NPV'].tolist()[0]\
        - price_breakdown.loc[price_breakdown['Name'] == 'Monetized tax losses','NPV'].tolist()[0]
    
    for key in self.feed_units.keys():
        if key in price_breakdown.loc[price_breakdown['Type']=='Operating Revenue', 'Name'].tolist():
            # revenue from feedstock (i.e. excess electricity)
            price_breakdown_feed[key] = -1 * price_breakdown.loc[price_breakdown['Name']==key,'NPV'].tolist()[0]
        else:
            price_breakdown_feed[key] = price_breakdown.loc[price_breakdown['Name']==key,'NPV'].tolist()[0]
    
    
    if gen_inflation > 0:
        price_breakdown_taxes = price_breakdown_taxes + price_breakdown.loc[price_breakdown['Name']=='Capital gains taxes payable','NPV'].tolist()[0]

    price_breakdown_financial_equipment = price_breakdown.loc[price_breakdown['Name']=='Repayment of debt','NPV'].tolist()[0]\
        + price_breakdown.loc[price_breakdown['Name']=='Interest expense','NPV'].tolist()[0]\
        + price_breakdown.loc[price_breakdown['Name']=='Dividends paid','NPV'].tolist()[0]\
        - price_breakdown.loc[price_breakdown['Name']=='Inflow of debt','NPV'].tolist()[0]\
        - price_breakdown.loc[price_breakdown['Name']=='Inflow of equity','NPV'].tolist()[0]    
        
    # Calculate remaining financial expenses
    price_breakdown_financial_remaining = price_breakdown.loc[price_breakdown['Name']=='Non-depreciable assets','NPV'].tolist()[0]\
        + price_breakdown.loc[price_breakdown['Name']=='Cash on hand reserve','NPV'].tolist()[0]\
        + price_breakdown.loc[price_breakdown['Name']=='Property tax and insurance','NPV'].tolist()[0]\
        - price_breakdown.loc[price_breakdown['Name']=='Sale of non-depreciable assets','NPV'].tolist()[0]\
        - price_breakdown.loc[price_breakdown['Name']=='Cash on hand recovery','NPV'].tolist()[0]
    
    # list containing all of the prices established above
    breakdown_prices = [*price_breakdown_capex.values(), 
                        price_breakdown_installation,
                        price_breakdown_labor_cost_annual, 
                        price_breakdown_labor_cost_maintenance, 
                        price_breakdown_labor_cost_admin_support, 
                        price_breakdown_maintenance_materials, 
                        *price_breakdown_feed.values(),
                        price_breakdown_taxes, 
                        price_breakdown_financial_equipment, 
                        price_breakdown_financial_remaining]
                
    price_breakdown_check = sum(breakdown_prices)
    # print(f'price breakdown (manual): {price_breakdown_check}')
        
    bos_savings = 0 * (price_breakdown_labor_cost_admin_support) * 0.3 # TODO is this applicable for cement?

    breakdown_prices.append(price_breakdown_check)
    breakdown_prices.append(bos_savings) 

    breakdown_categories = [*[f'{key} CAPEX' for key in price_breakdown_capex.keys()],
                            'Installation Cost',
                            'Annual Operating Labor Cost (including maintenance?)',
                            'Maintenance Labor Cost (zero at the moment?)',
                            'Administrative & Support Labor Cost',
                            # 'Property tax and insurance',
                            'Maintenance Materials',
                            *[f'{key} OPEX' for key in price_breakdown_feed.keys()],
                            'Taxes',
                            'Equipment Financing',
                            'Remaining Financial',
                            'Total',
                            'BOS Savings (copied from green steel)']
    
    if len(breakdown_categories) != len(breakdown_prices):
        raise Exception("categories and prices lists have to be the same length")

    cement_price_breakdown = dict()
    for category, price in zip(breakdown_categories, breakdown_prices):
        cement_price_breakdown[f'cement price: {category} ($/ton)'] = price

    return cement_price_breakdown

  