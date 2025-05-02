missions = {
    1:{
        "tasks": ["simple"], 
        "tokens": ["simple"]
    },
    2: {
        "tasks": ["numbered", "numbered", "simple", "simple"],  
        "tokens": ["numbered token 1", "numbered token 2", "simple task", "simple task"]
    },
    3: {
        "tasks": ["arrow", "arrow", "simple", "simple", "simple"],  
        "tokens": ["<", "<<", "simple task", "simple task", "simple task"]
    },
    4: {
        "tasks": ["simple", "simple", "simple", "omega"],  
        "tokens": ["simple task", "simple task", "simple task", "Ω"]
    },
    5: {
        "tasks": ["arrow", "arrow", "simple", "omega"],  
        "tokens": ["<", "<<", "simple task", "Ω"]
    },
    6: {
        "tasks": ["simple"],  
        "tokens": ["simple task"],
        "condition": ["deadzone"]  
    },
    7: {
        "tasks": ["numbered", "numbered", "simple", "simple"],  
        "tokens": ["numbered token 1", "numbered token 2", "simple task", "simple task"],
        "condition": ["disruption"]
    },
    8: {
        "tasks": ["simple", "simple", "simple", "omega"],  
        "tokens": ["simple task", "simple task", "simple task", "Ω"],
        "condition": ["commanders_decision"]  
    },
    9: {
        "tasks": ["numbered", "numbered", "simple", "simple"],  
        "tokens": ["numbered token 1", "numbered token 2", "simple task", "simple task"],
        "condition": ["commanders_distribution"]  
    },
    10: {
        "tasks": ["numbered", "numbered","arrow", "arrow", "simple", "omega"],  
        "tokens": ["numbered token 1", "numbered token 2","<", "<<", "simple task", "Ω"]
    },
}