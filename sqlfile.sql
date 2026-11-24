create database Apnacity ;
use apnacity ;
CREATE TABLE civic_complaints (
    Complaint_ID             VARCHAR(20) PRIMARY KEY,
    City                     VARCHAR(50),
    Area_Locality            VARCHAR(100),
    Zone               VARCHAR(50),
    Latitude                 DECIMAL(9,4),
    Longitude                DECIMAL(9,4),
    Issue                    VARCHAR(100),
    Category                 VARCHAR(50),
    Responsible_Authority    VARCHAR(50),
    Severity                 VARCHAR(20),      -- Medium / High / Critical
    AI_Confidence            DECIMAL(4,2),
    Similarity_Score         DECIMAL(4,2),
    Similar_Duplicate_Found  VARCHAR(3),       -- Yes / No
    Citizen_Support_Count    INT,
    NGO_Involved             VARCHAR(3),
    Citizen_Group_Active     VARCHAR(3),
    Escalation_Level         VARCHAR(50),      -- NULL for ~20 rows
    Complaint_Status         VARCHAR(20),      -- Pending / Assigned / In Progress / Escalated / Resolved
    Days_Open                INT,
    AI_Auto_Routed           VARCHAR(3),
    Evidence                 VARCHAR(50),
    Resolution_Verified      VARCHAR(3),
    Priority_Score           DECIMAL(5,2)
);
