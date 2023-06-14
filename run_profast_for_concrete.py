# template based on run_profast_for_steel.py
# Evan Sharafuddin

import ProFAST

def run_profast_for_concrete():

    #-------------------- values to import ---------------------
    plant_capacity_mtpy = 1000000 # metric tons per year
    plant_capacity_factor = 0.9 # account for shutdown due to maintenance
    concrete_production_mtpy = plant_capacity_mtpy*plant_capacity_factor

    # Should connect these to something (AEO, Cambium, etc.) ### not sure what this means...
    natural_gas_cost = 4                        # $/MMBTU
    electricity_cost = 48.92                    # $/MWh
    plant_life = 30

    # Hydrogen cost
    levelized_cost_of_hydrogen = 7              # $/kg
    natural_gas_cost = 4                        # $/MMBTU
    electricity_cost = 48.92                    # $/MWh

    
    #--------------------- Capital costs and Total Plant Cost ---------------------
    
    total_plant_cost = 1
                     
    
    #-------------------------------Fixed O&M Costs------------------------------
    
    total_fixed_operating_cost = 1
    
    #-------------------------- Feedstock and Waste Costs -------------------------
    
    
    
    # ---------------Feedstock Consumtion and Waste/Emissions Production-----------
    
    
    
    #---------------------- Owner's (Installation) Costs --------------------------
    labor_cost_fivemonth = 5/12*(labor_cost_annual_operation + labor_cost_maintenance \
                               + labor_cost_admin_support)
    
    maintenance_materials_onemonth = maintenance_materials_unitcost*plant_capacity_mtpy/12
    non_fuel_consumables_onemonth = plant_capacity_mtpy*(raw_water_consumption*raw_water_unitcost\
                                  + lime_consumption*lime_unitcost + carbon_consumption*carbon_unitcost\
                                  + iron_ore_consumption*iron_ore_pellet_unitcost)/12
        
    waste_disposal_onemonth = plant_capacity_mtpy*slag_disposal_unitcost*slag_production/12
    
    one_month_energy_cost_25percent = 0.25*plant_capacity_mtpy*(hydrogen_consumption*levelized_cost_of_hydrogen*1000\
                                    + natural_gas_consumption*natural_gas_cost/1.05505585\
                                    + electricity_consumption*electricity_cost)/12
    two_percent_tpc = 0.02*total_plant_cost
    
    fuel_consumables_60day_supply_cost = plant_capacity_mtpy*(raw_water_consumption*raw_water_unitcost\
                                  + lime_consumption*lime_unitcost + carbon_consumption*carbon_unitcost\
                                  + iron_ore_consumption*iron_ore_pellet_unitcost)/365*60
        
    spare_parts_cost = 0.005*total_plant_cost
    
    land_cost = 0.775*plant_capacity_mtpy
    misc_owners_costs = 0.15*total_plant_cost
    
    installation_cost = labor_cost_fivemonth + two_percent_tpc\
                       + fuel_consumables_60day_supply_cost + spare_parts_cost\
                       + misc_owners_costs
                       
    #total_overnight_capital_cost = total_plant_cost + total_owners_cost
        
    # Set up ProFAST
    pf = ProFAST.ProFAST('blank')
    
    # Fill these in - can have most of them as 0 also
    gen_inflation = 0.00
    pf.set_params('commodity',{"name":'Steel',"unit":"metric tonnes","initial price":1000,"escalation":gen_inflation})
    pf.set_params('capacity',plant_capacity_mtpy/365) #units/day
    pf.set_params('maintenance',{"value":0,"escalation":gen_inflation})
    pf.set_params('analysis start year',2022)
    pf.set_params('operating life',plant_life)
    pf.set_params('installation months',20)
    pf.set_params('installation cost',{"value":installation_cost,"depr type":"Straight line","depr period":4,"depreciable":False})
    pf.set_params('non depr assets',land_cost)
    pf.set_params('end of proj sale non depr assets',land_cost*(1+gen_inflation)**plant_life)
    pf.set_params('demand rampup',5.3)
    pf.set_params('long term utilization',plant_capacity_factor)
    pf.set_params('credit card fees',0)
    pf.set_params('sales tax',0) 
    pf.set_params('license and permit',{'value':00,'escalation':gen_inflation})
    pf.set_params('rent',{'value':0,'escalation':gen_inflation})
    pf.set_params('property tax and insurance percent',0)
    pf.set_params('admin expense percent',0)
    pf.set_params('total income tax rate',0.27)
    pf.set_params('capital gains tax rate',0.15)
    pf.set_params('sell undepreciated cap',True)
    pf.set_params('tax losses monetized',True)
    pf.set_params('operating incentives taxable',True)
    pf.set_params('general inflation rate',gen_inflation)
    pf.set_params('leverage after tax nominal discount rate',0.0824)
    pf.set_params('debt equity ratio of initial financing',1.38)
    pf.set_params('debt type','Revolving debt')
    pf.set_params('debt interest rate',0.0489)
    pf.set_params('cash onhand percent',1)
    
    #----------------------------------- Add capital items to ProFAST ----------------
    pf.add_capital_item(name="EAF & Casting",cost=capex_eaf_casting,depr_type="MACRS",depr_period=7,refurb=[0])
    pf.add_capital_item(name="Shaft Furnace",cost=capex_shaft_furnace,depr_type="MACRS",depr_period=7,refurb=[0])
    pf.add_capital_item(name="Oxygen Supply",cost=capex_oxygen_supply,depr_type="MACRS",depr_period=7,refurb=[0])
    pf.add_capital_item(name="H2 Pre-heating",cost=capex_h2_preheating,depr_type="MACRS",depr_period=7,refurb=[0])
    pf.add_capital_item(name="Cooling Tower",cost=capex_cooling_tower,depr_type="MACRS",depr_period=7,refurb=[0])
    pf.add_capital_item(name="Piping",cost=capex_piping,depr_type="MACRS",depr_period=7,refurb=[0])
    pf.add_capital_item(name="Electrical & Instrumentation",cost=capex_elec_instr,depr_type="MACRS",depr_period=7,refurb=[0])
    pf.add_capital_item(name="Buildings, Storage, Water Service",cost=capex_buildings_storage_water,depr_type="MACRS",depr_period=7,refurb=[0])
    pf.add_capital_item(name="Other Miscellaneous Costs",cost=capex_misc,depr_type="MACRS",depr_period=7,refurb=[0])

    total_capex = capex_eaf_casting+capex_shaft_furnace+capex_oxygen_supply+capex_h2_preheating+capex_cooling_tower+capex_piping+capex_elec_instr+capex_buildings_storage_water+capex_misc
    
    #-------------------------------------- Add fixed costs--------------------------------
    pf.add_fixed_cost(name="Annual Operating Labor Cost",usage=1,unit='$/year',cost=labor_cost_annual_operation,escalation=gen_inflation)
    pf.add_fixed_cost(name="Maintenance Labor Cost",usage=1,unit='$/year',cost=labor_cost_maintenance,escalation=gen_inflation)
    pf.add_fixed_cost(name="Administrative & Support Labor Cost",usage=1,unit='$/year',cost=labor_cost_admin_support,escalation=gen_inflation)
    pf.add_fixed_cost(name="Property tax and insurance",usage=1,unit='$/year',cost=0.02*total_plant_cost,escalation=0.0) 
    # Putting property tax and insurance here to zero out depcreciation/escalation. Could instead put it in set_params if
    # we think that is more accurate
    
    #---------------------- Add feedstocks, note the various cost options-------------------
    pf.add_feedstock(name='Maintenance Materials',usage=1.0,unit='Units per metric tonne of steel',cost=maintenance_materials_unitcost,escalation=gen_inflation)
    pf.add_feedstock(name='Raw Water Withdrawal',usage=raw_water_consumption,unit='metric tonnes of water per metric tonne of steel',cost=raw_water_unitcost,escalation=gen_inflation)
    pf.add_feedstock(name='Lime',usage=lime_consumption,unit='metric tonnes of lime per metric tonne of steel',cost=lime_unitcost,escalation=gen_inflation)
    pf.add_feedstock(name='Carbon',usage=carbon_consumption,unit='metric tonnes of carbon per metric tonne of steel',cost=carbon_unitcost,escalation=gen_inflation)
    pf.add_feedstock(name='Iron Ore',usage=iron_ore_consumption,unit='metric tonnes of iron ore per metric tonne of steel',cost=iron_ore_pellet_unitcost,escalation=gen_inflation)
    pf.add_feedstock(name='Hydrogen',usage=hydrogen_consumption,unit='metric tonnes of hydrogen per metric tonne of steel',cost=levelized_cost_of_hydrogen*1000,escalation=gen_inflation)
    pf.add_feedstock(name='Natural Gas',usage=natural_gas_consumption,unit='GJ-LHV per metric tonne of steel',cost=natural_gas_cost/1.05505585,escalation=gen_inflation)
    pf.add_feedstock(name='Electricity',usage=electricity_consumption,unit='MWh per metric tonne of steel',cost=electricity_cost,escalation=gen_inflation)
    pf.add_feedstock(name='Slag Disposal',usage=slag_production,unit='metric tonnes of slag per metric tonne of steel',cost=slag_disposal_unitcost,escalation=gen_inflation)

    pf.add_coproduct( name = 'Oxygen sales', usage = excess_oxygen, unit='kg O2 per metric tonne of steel', cost = oxygen_market_price, escalation=gen_inflation)
# Not sure if ProFAST can work with negative cost i.e., revenues so, will add the reduction at the end
    # if o2_heat_integration == 1:
    #     pf.addfeedstock(name='Oxygen Sales',usage=excess_oxygen,unit='kilograms of oxygen per metric tonne of steel',cost=-oxygen_market_price,escalation=gen_inflation)
    #------------------------------ Sovle for breakeven price ---------------------------
    
    sol = pf.solve_price()
    
    summary = pf.summary_vals
    
    price_breakdown = pf.get_cost_breakdown()
    
    price_breakdown_eaf_casting = price_breakdown.loc[price_breakdown['Name']=='EAF & Casting','NPV'].tolist()[0]
    price_breakdown_shaft_furnace = price_breakdown.loc[price_breakdown['Name']=='Shaft Furnace','NPV'].tolist()[0]  
    price_breakdown_oxygen_supply = price_breakdown.loc[price_breakdown['Name']=='Oxygen Supply','NPV'].tolist()[0] 
    price_breakdown_h2_preheating = price_breakdown.loc[price_breakdown['Name']=='H2 Pre-heating','NPV'].tolist()[0]     
    price_breakdown_cooling_tower = price_breakdown.loc[price_breakdown['Name']=='Cooling Tower','NPV'].tolist()[0] 
    price_breakdown_piping = price_breakdown.loc[price_breakdown['Name']=='Piping','NPV'].tolist()[0] 
    price_breakdown_elec_instr = price_breakdown.loc[price_breakdown['Name']=='Electrical & Instrumentation','NPV'].tolist()[0] 
    price_breakdown_buildings_storage_water = price_breakdown.loc[price_breakdown['Name']=='Buildings, Storage, Water Service','NPV'].tolist()[0]  
    price_breakdown_misc = price_breakdown.loc[price_breakdown['Name']=='Other Miscellaneous Costs','NPV'].tolist()[0]
    price_breakdown_installation = price_breakdown.loc[price_breakdown['Name']=='Installation cost','NPV'].tolist()[0]
 
    
    price_breakdown_labor_cost_annual = price_breakdown.loc[price_breakdown['Name']=='Annual Operating Labor Cost','NPV'].tolist()[0]  
    price_breakdown_labor_cost_maintenance = price_breakdown.loc[price_breakdown['Name']=='Maintenance Labor Cost','NPV'].tolist()[0]  
    price_breakdown_labor_cost_admin_support = price_breakdown.loc[price_breakdown['Name']=='Administrative & Support Labor Cost','NPV'].tolist()[0] 
    #price_breakdown_proptax_ins = price_breakdown.loc[price_breakdown['Name']=='Property tax and insurance','NPV'].tolist()[0]
    
    price_breakdown_maintenance_materials = price_breakdown.loc[price_breakdown['Name']=='Maintenance Materials','NPV'].tolist()[0]  
    price_breakdown_water_withdrawal = price_breakdown.loc[price_breakdown['Name']=='Raw Water Withdrawal','NPV'].tolist()[0] 
    price_breakdown_lime = price_breakdown.loc[price_breakdown['Name']=='Lime','NPV'].tolist()[0]
    price_breakdown_carbon = price_breakdown.loc[price_breakdown['Name']=='Carbon','NPV'].tolist()[0]
    price_breakdown_iron_ore = price_breakdown.loc[price_breakdown['Name']=='Iron Ore','NPV'].tolist()[0]
    if levelized_cost_of_hydrogen < 0:
        price_breakdown_hydrogen = -1*price_breakdown.loc[price_breakdown['Name']=='Hydrogen','NPV'].tolist()[0]
    else:
        price_breakdown_hydrogen = price_breakdown.loc[price_breakdown['Name']=='Hydrogen','NPV'].tolist()[0]
    price_breakdown_natural_gas = price_breakdown.loc[price_breakdown['Name']=='Natural Gas','NPV'].tolist()[0]
    price_breakdown_electricity = price_breakdown.loc[price_breakdown['Name']=='Electricity','NPV'].tolist()[0]
    price_breakdown_slag =  price_breakdown.loc[price_breakdown['Name']=='Slag Disposal','NPV'].tolist()[0]
    price_breakdown_taxes = price_breakdown.loc[price_breakdown['Name']=='Income taxes payable','NPV'].tolist()[0]\
        - price_breakdown.loc[price_breakdown['Name'] == 'Monetized tax losses','NPV'].tolist()[0]\
    
    if o2_heat_integration == 1:
        price_breakdown_O2sales =  price_breakdown.loc[price_breakdown['Name']=='Oxygen sales','NPV'].tolist()[0]    
    else:
        price_breakdown_O2sales = 0
        
    if gen_inflation > 0:
        price_breakdown_taxes = price_breakdown_taxes + price_breakdown.loc[price_breakdown['Name']=='Capital gains taxes payable','NPV'].tolist()[0]
        
    # price_breakdown_financial = price_breakdown.loc[price_breakdown['Name']=='Non-depreciable assets','NPV'].tolist()[0]\
    #     + price_breakdown.loc[price_breakdown['Name']=='Cash on hand reserve','NPV'].tolist()[0]\
    #     + price_breakdown.loc[price_breakdown['Name']=='Property tax and insurance','NPV'].tolist()[0]\
    #     + price_breakdown.loc[price_breakdown['Name']=='Repayment of debt','NPV'].tolist()[0]\
    #     + price_breakdown.loc[price_breakdown['Name']=='Interest expense','NPV'].tolist()[0]\
    #     + price_breakdown.loc[price_breakdown['Name']=='Dividends paid','NPV'].tolist()[0]\
    #     - price_breakdown.loc[price_breakdown['Name']=='Sale of non-depreciable assets','NPV'].tolist()[0]\
    #     - price_breakdown.loc[price_breakdown['Name']=='Cash on hand recovery','NPV'].tolist()[0]\
    #     - price_breakdown.loc[price_breakdown['Name']=='Inflow of debt','NPV'].tolist()[0]\
    #     - price_breakdown.loc[price_breakdown['Name']=='Inflow of equity','NPV'].tolist()[0]

    # Calculate financial expense associated with equipment
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
    

    price_breakdown_check = price_breakdown_eaf_casting+price_breakdown_shaft_furnace+price_breakdown_oxygen_supply+price_breakdown_h2_preheating\
            +price_breakdown_cooling_tower+price_breakdown_piping+price_breakdown_elec_instr+price_breakdown_buildings_storage_water+price_breakdown_misc\
            +price_breakdown_installation+price_breakdown_labor_cost_annual+price_breakdown_labor_cost_maintenance+price_breakdown_labor_cost_admin_support\
            +price_breakdown_maintenance_materials+price_breakdown_water_withdrawal+price_breakdown_lime+price_breakdown_carbon+price_breakdown_iron_ore\
            +price_breakdown_hydrogen+price_breakdown_natural_gas+price_breakdown_electricity+price_breakdown_slag+price_breakdown_taxes+price_breakdown_financial_equipment\
            +price_breakdown_financial_remaining+price_breakdown_O2sales    # a neater way to implement is add to price_breakdowns but I am not sure if ProFAST can handle negative costs
 
        
    bos_savings =  (price_breakdown_labor_cost_admin_support) * 0.3
    steel_price_breakdown = {'Steel price: EAF and Casting CAPEX ($/tonne)':price_breakdown_eaf_casting,'Steel price: Shaft Furnace CAPEX ($/tonne)':price_breakdown_shaft_furnace,\
                             'Steel price: Oxygen Supply CAPEX ($/tonne)':price_breakdown_oxygen_supply,'Steel price: H2 Pre-heating CAPEX ($/tonne)':price_breakdown_h2_preheating,\
                          'Steel price: Cooling Tower CAPEX ($/tonne)':price_breakdown_cooling_tower,'Steel price: Piping CAPEX ($/tonne)':price_breakdown_piping,\
                          'Steel price: Electrical & Instrumentation ($/tonne)':price_breakdown_elec_instr,'Steel price: Buildings, Storage, Water Service CAPEX ($/tonne)':price_breakdown_buildings_storage_water,\
                          'Steel price: Miscellaneous CAPEX ($/tonne)':price_breakdown_misc,'Steel price: Annual Operating Labor Cost ($/tonne)':price_breakdown_labor_cost_annual,\
                          'Steel price: Maintenance Labor Cost ($/tonne)':price_breakdown_labor_cost_maintenance,'Steel price: Administrative & Support Labor Cost ($/tonne)':price_breakdown_labor_cost_admin_support,\
                          'Steel price: Installation Cost ($/tonne)':price_breakdown_installation,'Steel price: Maintenance Materials ($/tonne)':price_breakdown_maintenance_materials,\
                          'Steel price: Raw Water Withdrawal ($/tonne)':price_breakdown_water_withdrawal,'Steel price: Lime ($/tonne)':price_breakdown_lime,\
                          'Steel price: Carbon ($/tonne)':price_breakdown_carbon,'Steel price: Iron Ore ($/tonne)':price_breakdown_iron_ore,\
                          'Steel price: Hydrogen ($/tonne)':price_breakdown_hydrogen,'Steel price: Natural gas ($/tonne)':price_breakdown_natural_gas,\
                          'Steel price: Electricity ($/tonne)':price_breakdown_electricity,'Steel price: Slag Disposal ($/tonne)':price_breakdown_slag,\
                          'Steel price: Taxes ($/tonne)':price_breakdown_taxes,'Steel price: Equipment Financing ($/tonne)':price_breakdown_financial_equipment,\
                          'Steel price: Remaining Financial ($/tonne)':price_breakdown_financial_remaining,'Steel price: Oxygen sales ($/tonne)': price_breakdown_O2sales,\
                          'Steel price: Total ($/tonne)':price_breakdown_check, '(-) Steel price: BOS savings ($/tonne)': bos_savings}
    
    price_breakdown = price_breakdown.drop(columns=['index','Amount'])

    return(sol,summary,price_breakdown,steel_production_mtpy,steel_price_breakdown,total_capex)






