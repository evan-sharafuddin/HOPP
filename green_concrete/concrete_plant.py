"""
Created on Wed July 24 2:27 2023

@author: evan-sharafuddin
"""
class ConcretePlant:
    '''
    Class for green concrete analysis, requires a CementPlant instance

    TODO use inheretance or some sort of abstract class structure to make this cleaner?

    Source: https://www.nrmca.org/wp-content/uploads/2022/02/NRMCA_LCAReportV3-2_20220224.pdf

    '''

    def __init__(
        self, 
        cement_plant,
        concrete_strength,
        concrete_mixture,
    ):
        pass
        # TODO work on this if have time
        #   plan on using the OPC cli/cem scenario for the cement plant, and copying over the various
        #   LCAs for the concrete mixtures given in NRMCA
        #   rudimenary cost analysis by pulling TPC and then costs of feeds