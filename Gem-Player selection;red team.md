This analysis addresses the shortcomings in the current player allocation methodology, which leads to an unbalanced distribution of "Green" category players and violates the intended constraints. Based on the "Red Team" analysis and the newly defined rules, this document outlines a revised conceptual framework for the Python script's allocation logic.

The goal is to ensure social pairings are maintained, Green players are used strategically to balance teams with high 'Red' concentrations, and a strict cap on Green players per team is enforced.

### **The Core Conceptual Shift**

The fundamental change is moving from a generalized assignment process based purely on team size (the current "round-robin" approach) to a **prioritized, constraint-based** assignment process. This requires analyzing the *composition* of the teams during the allocation process and handling the most constrained players (Green) first.

### **Revised Logical Framework: Constraint-Aware Preferential Assignment**

We will retain the overall structure but significantly overhaul the preparation and the final "Filler" assignment phase.

#### **Phase 0: Pre-processing \- The "Group" Strategy (Crucial Addition)**

To robustly handle the "Child-to-child (Relationship)" rule, the fundamental unit of allocation must be the "Group," not the individual player.

1. **Identify Groups:** Before any allocation, the Python script must process the PairedWith data to link players into inseparable groups. A Group can be a single individual or a set of linked players.  
2. **Calculate Group Attributes:** For each Group, determine its aggregate characteristics:  
   * Group\_Size: Total number of players in the group.  
   * Group\_Composition: Count of Red, Green, Blue, Pink players in the group.  
   * Group\_Tiers and Group\_Is\_Tentpole.  
3. **Allocation Principle:** All subsequent steps allocate these Groups, not individuals.

#### **Phase 1 & 2: Foundation and Depth (Pod Rule)**

These phases establish the initial team structure based on the "Coach on first pass (Pod)" rule, utilizing the Group strategy.

1. **Determine Team Structure:** Calculate the required number of Red and Blue teams.  
2. **Assign Cores and Tentpoles:** Place foundational Tier 1 pairs and Tentpole groups.  
3. **Build Depth:** Add remaining Red groups to Red teams and Blue groups to Blue teams.

*Note:* If a mixed-color group (e.g., Red-Green pair) is assigned in this phase, the pairing constraint takes precedence over the balance/tenure rules.

#### **Phase 3: Strategic Filler Distribution (The Overhaul)**

This phase replaces the simple round-robin. It requires the script to dynamically track the composition of each team (Current\_Red\_Count, Current\_Green\_Count, Current\_Pink\_Count, Current\_Size) as assignments are made.

**Stage 3A: Targeted Green Distribution (Balance and Tenure Rules)**

Groups containing Green players must be prioritized.

1. **Identify Green Groups:** Isolate all unassigned groups containing one or more Green players.  
2. **Prioritized Allocation Loop:** Iterate through these Green groups (processing larger groups first).  
   * **Hard Constraint Check (Filtering):** Disqualify a team if:  
     * Current\_Size \+ Group\_Size \> MAX\_TEAM\_SIZE.  
     * **Tenure Rule:** Current\_Green\_Count \+ Group\_Count\_Green \> 2\.  
   * **Preference Ranking (Scoring):** Rank the remaining valid teams. We interpret "lots of Red" as the absolute count of Red players.  
     * **Primary Preference (Red-to-Green Balance):** Highest Current\_Red\_Count (Descending).  
     * **Secondary Preference (Overall Balance):** Smallest Current\_Size (Ascending).  
   * **Assignment:** Assign the Green group to the highest-ranking team and update statistics.  
   * **Flag for Relaxation:** If no valid teams exist, move the group to the Relaxation\_Pool.

**Stage 3B: Constraint Relaxation (Triage Mode)**

If groups remain in the Relaxation\_Pool, the constraints must be relaxed to ensure all players are placed.

1. **Relax Tenure Rule:** Temporarily ignore the "Max 2 Green" constraint.  
2. **Relaxed Assignment Loop:** Iterate through groups in the Relaxation\_Pool.  
   * **Hard Constraint Check (Filtering):** Disqualify teams only if the Size constraint is violated.  
   * **Minimization Ranking (Scoring):** Rank the valid teams to minimize the violation while maintaining balance.  
     * **Primary Preference (Minimize Violation):** Lowest Current\_Green\_Count (Ascending). (e.g., prefer adding a 3rd Green over a 4th).  
     * **Secondary Preference (Red-to-Green Balance):** Highest Current\_Red\_Count (Descending).  
     * **Tertiary Preference (Overall Balance):** Smallest Current\_Size (Ascending).  
   * **Assignment:** Assign the group and log a warning that the constraint was violated.

**Stage 3C: Remaining Filler Distribution (Pink and Others)**

Once all Green groups are assigned, distribute the remaining fillers.

1. **Identify Remaining Groups:** Isolate remaining unassigned groups.  
2. **Allocation Loop:** Iterate through the remaining groups.  
   * **Hard Constraint Check (Filtering):** Disqualify teams if the Size constraint is violated.  
   * **Preference Ranking (Scoring):** Rank the valid teams aiming for overall balance and even distribution.  
     * **Primary Preference (Pink Distribution):** Lowest Current\_Pink\_Count (Ascending).  
     * **Secondary Preference (Overall Balance):** Smallest Current\_Size (Ascending).  
     * **Tertiary Preference (Slight Bias):** Preference for Red teams over Blue teams if sizes are equal.  
   * **Assignment:** Assign the group and update statistics.