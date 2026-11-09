from cellularautomata import GuiCA, CountType
from random import random
import math
import tkinter as tk
from tkinter import simpledialog


#  PART 1: ADMINISTRATION SELECTION 

root = tk.Tk()
root.withdraw()

choice = simpledialog.askstring(
    "Administration Mode",
    "Choose the administration mode:\n\n"
    "1. Oral\n"
    "2. Nano\n"
    "3. IV\n\n"
    "Enter 1, 2 or 3:"
)
root.destroy()

ROUTE = {"1": "ORAL", "2": "NANO", "3": "IV"}.get(
    choice.strip() if choice else "1", "ORAL"
)

ROUTE_ORAL = ROUTE == "ORAL"
ROUTE_NANO = ROUTE == "NANO"
ROUTE_IV   = ROUTE == "IV"


# PART 2: BIOLOGICAL SCENARIO  
# Set exactly ONE to True, the rest to False.

SCENARIO_TNBC        = False
SCENARIO_EPI_ONLY    = False
SCENARIO_FERRO_ONLY  = False
SCENARIO_NO_TREAT    = True

SCENARIO_DEFAULT = not any([
    SCENARIO_TNBC,
    SCENARIO_EPI_ONLY,
    SCENARIO_FERRO_ONLY,
    SCENARIO_NO_TREAT
])


# BASE BIOLOGICAL PARAMETERS 

BETA = 0.10     # neighbourhood-driven cancer progression strength/ proliferation rate
RHO  = 0.02     # baseline immune clearance

if SCENARIO_TNBC:       # TNBC is the most aggressive breast cancer sub-type
    BETA = 0.15         # increased proliferation rate in TNBC via Hedgehog/Glil pathways
    RHO  = 0.01         # reduced immune clearance, due to stronger immune evasion in TNBC

# t = simulation step counter (incremented once per full grid step, not per cell)
t          = 0
_call_count = 0
_GRID_SIZE  = 50  # must match Size slider value


#  D(t) : Effective curcumin drug activity over time per administration route 

def DrugField(t, route):
    if route == "ORAL":     # If curcumin administrated via oral route
        # Bateman curve: delayed absorption, rapid hepatic degradation/ metabolism.
        # Low peak, fast decay. Low bioavailability (< 1%).
        D0 = 0.20       # low initial curcumin exposure
        k  = 0.10       #decay rate of effective curcumin activity
        return min(D0 * t * math.exp(-k * t), 1.0)      # rise and fall type pharmacokinetic profile

    elif route == "NANO":       # If curcumin administrated via nanoparticules
        # Sigmoidal rise then very slow sustained release.
        # Nanoparticles bypass first-pass metabolism via EPR + HA-CD44 targeting.
        # Higher plateau and much slower decay than IV. Better bio-availabilty than Oral and IV route.
        D0     = 0.85       #high initial curcumin exposure
        k_rise = 0.15       # gradual accumulation/release rate
        k_fall = 0.005      # slow clearence rate
        return D0 * (1 - math.exp(-k_rise * t)) * math.exp(-k_fall * t)     #sigmoid increase and slow decay

    elif route == "IV":     # If curcumin administrated via intravenous route
        # Rapid rise to high peak then moderate decay.
        # Direct bloodstream delivery, no absorption barrier.
        D0     = 0.95       # very high initial curcumin exposure
        k_rise = 0.30       # fast systemic availability
        k_fall = 0.020      # moderate decay rate of effective curcumin activity
        return D0 * (1 - math.exp(-k_rise * t)) * math.exp(-k_fall * t)     #fast rise and exponential decay

    else:       # administration route unspecified or unknown
        return 0.50 * math.exp(-0.015 * t)      # generic expoential decay profile, with weak residual anti-tumor activity


#  SCENARIO-DEPENDENT PARAMETERS 

if SCENARIO_TNBC:       # Scenario 3: Triple-negative breast cancer, the most aggressive sub-type
    if ROUTE_ORAL:          # if oral administration of curcumin
        gamma_admin = 0.20      # low bio-availability, low drug delivery due fast metabolism by oral adminisatration of curcumin
    elif ROUTE_NANO:        # if administration via nanoparticules
        gamma_admin = 0.85      # high bio-availability, better drug delivery and absorption
    elif ROUTE_IV:      # if adminisatration via intravenous route
        gamma_admin = 0.70      # better bio-availabilty than oral route, because IV route bypasses metabolism
    else:
        gamma_admin = 0.20      # by default, if no admnisatrtion route is specified
    EPI              = 0.20     # In TNBC, we have reduced value of epigenetic pathway, because TNBC epigenome is less responsive to DNMT inhibition
    T_treat          = 8        # Long steps to overcome cellular resistance
    CURCUMIN_PRESENT = True     # curcumin is administered

elif SCENARIO_EPI_ONLY:     # Scenario 2 : Epigenetic pathway only
    gamma_admin      = 0.0      # sets S_eff to 0, and disables ferroptosis
    EPI              = 0.45     # full epigenetic pathway enabled
    T_treat          = 6        # timer for steps between DNMT1 inhibition and cell death
    CURCUMIN_PRESENT = True     # curcumin is administered

elif SCENARIO_FERRO_ONLY:       # Scenario 1 : Ferroptosis pathway only
    gamma_admin      = 0.70     # moderate drug delivery
    EPI              = 0.0      # epigenetic pathway disabled
    T_treat          = 6        # timer not used here, because ferroptosis kills directly
    CURCUMIN_PRESENT = True     # curcumin is administered

elif SCENARIO_NO_TREAT:     # Scenario 4: No treatement with curcumin (control group)
    gamma_admin      = 0.0      # no drug delivery of curcumin
    EPI              = 0.0      # no epigenetic effect
    T_treat          = 6        # timer not used here, because no treatement applied
    CURCUMIN_PRESENT = False    # curcumin is not administered

else:           # scenario by default
    if ROUTE_ORAL:      # if administration of curcumin via oral route
        gamma_admin = 0.20      # low drug delivery due to low bio-availability
    elif ROUTE_NANO:        # if administration of curcumin via nanoparticules 
        gamma_admin = 0.85      # better drug delivery and absoprtion due to high bio-availability 
    elif ROUTE_IV:      # if administration of curcumin via intravenous route
        gamma_admin = 0.70      # higher drug delivery and bio-availability due to bypass of metabolism
    else:       # administration route unspecified or unknown
        gamma_admin = 0.20      # low drug delivery by default (oral)
    EPI              = 0.45     # epigenetic effect enabled by default
    T_treat          = 10 if ROUTE_NANO else 6      # set timer for scenario by default
    CURCUMIN_PRESENT = True     # curcumin is administered by default 


#  DERIVED PARAMETERS 

S_eff = 0.25 * gamma_admin      # effective tumor suppressive strength of curcumin 

def gamma_ferro(D):     # probability of ferroptosis induction, increases with drug activity
    return min(0.30, 0.03 + 0.27 * D)

def gamma_epi(D):       # probabilty of epigenetic-mediated apoptosis, increases with drug activity
    return min(0.20, 0.02 + 0.18 * D)

gamma_reg = 0.05    # proba an empty cell becomes healthy due to tissue regneration
N_H_min   = 3       # minimum number of healthy cells required to trigger regeneration


#  CELL RULE FUNCTION 

def BreastCancerCurcumin(cell, neighbors):
    global t, _call_count, _GRID_SIZE

    # Increment t once per full grid step (every _GRID_SIZE² cell calls)
    _call_count += 1
    if _call_count % (_GRID_SIZE * _GRID_SIZE) == 0:
        t += 1

    category, timer = cell
    D = DrugField(t, ROUTE)

    match category:

        # RULE 1: HEALTHY → CANCEROUS
        # BETA higher in TNBC (via Hedgehog/Gli1 signalling) → faster invasion
        case 'Healthy':
            if CountType(neighbors, 'Cancerous') > 0 and random() < (RHO + BETA):
                return ('Cancerous', None)
            return cell

        # RULE 2: CANCEROUS
        case 'Cancerous':

            # RULE 2a: Curcumin induced epigenetic treatment. Cancerous → Treated (DNMT1 inhibition, slow death)
            # Disabled in FERRO_ONLY (EPI=0) and NO_TREAT
            if CURCUMIN_PRESENT and random() < (S_eff * D) and random() < EPI:
                return ('Treated', T_treat)

            # RULE 2b: Ferroptotic direct kill (SLC1A5 → lipid ROS → death). Cancerous → Dead 
            # Disabled in EPI_ONLY (S_eff=0) and NO_TREAT
            if CURCUMIN_PRESENT and random() < gamma_ferro(D):
                return ('Dead', None)

            # RULE 2c: Epigenetic rapid apoptosis (HDAC inhibition). Cancer → Dead
            # Disabled when EPI=0
            if CURCUMIN_PRESENT and EPI > 0 and random() < gamma_epi(D):
                return ('Dead', None)

            # RULE 2d: Immune baseline death. Cancer → Dead
            # RHO=0.01 in TNBC (stronger immune evasion)
            if random() < RHO:
                return ('Dead', None)

            # RULE 2e: Cancer proliferation into healthy tissue. Healthy → Cancer
            # BETA=0.15 in TNBC → more aggressive expansion
            if CountType(neighbors, 'Healthy') > 0 and random() < 0.45:
                return ('Cancerous', None)

            return cell

        # RULE 3: TREATED → DEAD
        # T_treat=8 in TNBC (longer resistance to overcome)
        case 'Treated':
            if timer is None:
                timer = T_treat
            if timer <= 0:
                return ('Dead', None)
            else:
                return ('Treated', timer - 1)

        # RULE 4: DEAD → EMPTY
        case 'Dead':
            return ('Empty', None)

        # RULE 5: EMPTY → HEALTHY (conditional regeneration)
        # Blocked while cancer present nearby
        case 'Empty':
            h_count      = CountType(neighbors, 'Healthy')
            cancer_count = CountType(neighbors, 'Cancerous')
            if h_count >= N_H_min and cancer_count == 0:
                if random() < gamma_reg:
                    return ('Healthy', None)
            return cell

        case _:
            return cell


#  CELL STATE COLORS 
cellcolors = {
    ('Empty',     None): 'white',
    ('Healthy',   None): 'lightgreen',
    ('Cancerous', None): 'firebrick',
    ('Treated',   None): 'goldenrod',
    ('Dead',      None): 'dimgray',
}

GuiCA(BreastCancerCurcumin, cellcolors)