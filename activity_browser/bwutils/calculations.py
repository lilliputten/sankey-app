# -*- coding: utf-8 -*-
# from ..bwutils import (
#     Contributions, MonteCarloLCA, MLCA, PresamplesMLCA,
#     PresamplesContributions, SuperstructureContributions,
#     SuperstructureMLCA,
# ) #TODO ps
from ..bwutils import (
    Contributions, MonteCarloLCA, MLCA,
    SuperstructureContributions, SuperstructureMLCA,
)

from bw2calc.errors import BW2CalcError


def do_LCA_calculations(data: dict):
    """Perform the MLCA calculation."""
    cs_name = data.get('cs_name', 'new calculation')
    calculation_type = data.get('calculation_type', 'simple')

    if calculation_type == 'simple':
        try:
            mlca = MLCA(cs_name)
            contributions = Contributions(mlca)
        except KeyError as e:
            raise BW2CalcError("LCA Failed", str(e)).with_traceback(e.__traceback__)
    # elif calculation_type == 'presamples': #TODO ps
    #     try:
    #         mlca = PresamplesMLCA(cs_name, data.get('data'))
    #         contributions = PresamplesContributions(mlca)
    #     except IndexError as e:
    #         # Occurs when a presamples package is used that refers to old
    #         # or non-existing array indices.
    #         msg = ("Given scenario package refers to non-existent exchanges."
    #                " It is suggested to remove or edit this package.")
    #         raise BW2CalcError(msg, str(e)).with_traceback(e.__traceback__)
    #     except KeyError as e:
    #         raise BW2CalcError("LCA Failed", str(e)).with_traceback(e.__traceback__)
    elif calculation_type == 'scenario':
        try:
            df = data.get('data')
            mlca = SuperstructureMLCA(cs_name, df)
            contributions = SuperstructureContributions(mlca)
        except AssertionError as e:
            # This occurs if the superstructure itself detects something is wrong.
            raise BW2CalcError("Scenario LCA failed.", str(e)).with_traceback(e.__traceback__)
        except ValueError as e:
            # This occurs if the LCA matrix does not contain any of the
            # exchanges mentioned in the superstructure data.
            raise BW2CalcError(
                "Scenario LCA failed.",
                "Constructed LCA matrix does not contain any exchanges from the superstructure"
            ).with_traceback(e.__traceback__)
        except KeyError as e:
            raise BW2CalcError("LCA Failed", str(e)).with_traceback(e.__traceback__)
    else: #TODO ps
        print('Calculation type must be: simple, presamples, or scenario. Given:', cs_name)
        raise ValueError

    mlca.calculate()
    mc = MonteCarloLCA(cs_name)

    return mlca, contributions, mc