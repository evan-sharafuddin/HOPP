def eur2013(multiplyer, *costs):
    ''' 
    Converts monetary values from EUR to USD

    multiplyer argument allows you to account for prefix (ex: M, k)

    works for individual values or an iterable of values

    NOTE: conversion factor is the average from 2013, which was the cost basis
    year given in the paper

    source: https://www.exchangerates.org.uk/EUR-USD-spot-exchange-rates-history-2013.html

    '''
    conversion_factor = 1.3284 # USD/EUR
    vals = []
    for cost in costs:
        vals.append(cost * conversion_factor * multiplyer)
    
    if len(vals) == 1:
        return vals[0]
    return vals

def eur2014(multiplyer, *costs):
    ''' 
    Converts monetary values from EUR to USD

    multiplyer argument allows you to account for prefix (ex: M, k)

    works for individual values or an iterable of values

    NOTE: conversion factor is the average from 2014, which was the cost basis
    year given in the paper

    source: https://www.exchangerates.org.uk/EUR-USD-spot-exchange-rates-history-2014.html

    '''
    conversion_factor = 1.3283 # USD/EUR
    vals = []
    for cost in costs:
        vals.append(cost * conversion_factor * multiplyer)
    
    if len(vals) == 1:
        return vals[0]
    return vals

def btu_to_j(multiplyer, *vals):
    '''
    Converts energy values from BTU to J

    multiplyer argment allows you to account for prefix (ex: M, k)

    '''

    vals_j = []
    for val in vals:
        vals_j.append(val * 1055.6 * multiplyer)

    if len(vals_j) == 1:
        return vals_j[0]
    return vals_j