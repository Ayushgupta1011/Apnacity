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

USE civic_db;
-- simulated data insertion
INSERT INTO civic_complaints (
    Complaint_ID, City, Area_Locality, Zone,
    Latitude, Longitude, Issue, Category,
    Responsible_Authority, Severity, AI_Confidence,
    Similarity_Score, Similar_Duplicate_Found,
    Citizen_Support_Count, NGO_Involved,
    Citizen_Group_Active, Escalation_Level,
    Complaint_Status, Days_Open, AI_Auto_Routed,
    Evidence, Resolution_Verified, Priority_Score
)
VALUES
('DEL-CIV-0001','Delhi','Dwarka','South West Delhi',28.5916,77.045,'Overflowing Garbage','Waste Management','MCD','High',0.85,0.71,'No',5,'No','No',NULL,'Pending',3,'Yes','Photo + Location','No',1.09),
('DEL-CIV-0002','Delhi','Rohini','North West Delhi',28.7495,77.056,'Pothole','Roads','PWD Delhi','High',0.92,0.82,'No',8,'No','No','Department Reminder','Assigned',5,'Yes','Photo + Location','No',1.36),
('DEL-CIV-0003','Delhi','Saket','South Delhi',28.5249,77.2066,'Broken Streetlight','Street Lighting','MCD','Medium',0.78,0.93,'Yes',11,'No','No','Senior Officer','In Progress',7,'Yes','Photo + Location','No',1.31),
('DEL-CIV-0004','Delhi','Lajpat Nagar','South East Delhi',28.5687,77.2438,'Water Leakage','Water Supply','Delhi Jal Board','High',0.85,0.64,'No',14,'Yes','No','NGO Review','Escalated',9,'Yes','Photo + Location','No',1.62),
('DEL-CIV-0005','Delhi','Karol Bagh','Central Delhi',28.6504,77.1917,'Illegal Dumping','Waste Management','MCD','High',0.92,0.75,'No',17,'No','No','Citizen Group','Resolved',11,'Yes','Photo + Location','Yes',1.97),
('DEL-CIV-0006','Delhi','Janakpuri','West Delhi',28.6214,77.0893,'Blocked Drain','Drainage','MCD','High',0.78,0.86,'Yes',20,'No','Yes',NULL,'Pending',13,'Yes','Photo + Location','No',1.86),
('DEL-CIV-0007','Delhi','Shahdara','East Delhi',28.6737,77.2875,'Damaged Footpath','Roads','MCD','Medium',0.85,0.97,'No',23,'No','No','Department Reminder','Assigned',15,'Yes','Photo + Location','No',2.25),
('DEL-CIV-0008','Delhi','Pitampura','North West Delhi',28.7038,77.1312,'Open Manhole','Drainage','MCD','Critical',0.92,0.68,'No',26,'Yes','No','Senior Officer','In Progress',17,'Yes','Photo + Location','No',2.69),
('DEL-CIV-0009','Delhi','Mayur Vihar','East Delhi',28.609,77.2922,'Stray Animal Concern','Animal Welfare','MCD','Medium',0.78,0.79,'Yes',4,'No','No','NGO Review','Escalated',19,'Yes','Photo + Location','No',1.44),
('DEL-CIV-0010','Delhi','Vasant Kunj','South West Delhi',28.5283,77.154,'Air Pollution','Environment','DPCC','High',0.85,0.90,'No',7,'No','No','Citizen Group','Resolved',1,'Yes','Photo + Location','Yes',1.08);

select * from civic_complaints ;
