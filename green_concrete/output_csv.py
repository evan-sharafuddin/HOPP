import pandas as pd
import os.path
from datetime import datetime

def output_csv(dir, *dicts):
    '''
    Creates a .csv file for results formatted in a dictionary. 

    The input dictionaries must have the following information
        values must not be any type of list/iterable (i.e. only floats, strings, etc)
        must have the the following key value pair:
            key: "TITLE", value $SECTION_TITLE$
            $SECTION_TITLE$ will label the type of data the dictionary contains in the .csv
    
    '''
    dfs = []
    
    for d in dicts:
        if not ("TITLE" in d.keys()):
            title = "TITLE"
        else:
            title = d["TITLE"]
            del d["TITLE"]
        
        data = {title: d.keys(), '': d.values()}
        df = pd.DataFrame.from_dict(data)
        dfs.append(df)

    now = datetime.now()
    dt_string = now.strftime("%d-%m-%Y_%H%M.%S")

    output = pd.concat(dfs, axis=1)
    output.fillna('')
    filename = 'cement_output_data_' + dt_string + '.csv'
    print(filename)
    path = os.path.join(dir, filename)
    
    output.to_csv(path)