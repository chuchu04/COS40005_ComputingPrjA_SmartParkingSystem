-- ============================================================
-- SmartParkingDb — Full SQL Schema (MySQL)
-- Generated from EF Core migration: 20260225094143_InitialCreate
-- Target: MySQL / phpMyAdmin
-- ============================================================

SET FOREIGN_KEY_CHECKS = 0;

-- ============================================================
-- 1. ASP.NET Identity Tables
-- ============================================================

CREATE TABLE AspNetUsers (
    Id                   VARCHAR(255)     NOT NULL,
    UserName             VARCHAR(256)     NULL,
    NormalizedUserName   VARCHAR(256)     NULL,
    Email                VARCHAR(256)     NULL,
    NormalizedEmail      VARCHAR(256)     NULL,
    EmailConfirmed       TINYINT(1)       NOT NULL DEFAULT 0,
    PasswordHash         TEXT             NULL,
    SecurityStamp        TEXT             NULL,
    ConcurrencyStamp     TEXT             NULL,
    PhoneNumber          TEXT             NULL,
    PhoneNumberConfirmed TINYINT(1)       NOT NULL DEFAULT 0,
    TwoFactorEnabled     TINYINT(1)       NOT NULL DEFAULT 0,
    LockoutEnd           DATETIME         NULL,
    LockoutEnabled       TINYINT(1)       NOT NULL DEFAULT 0,
    AccessFailedCount    INT              NOT NULL DEFAULT 0,
    PRIMARY KEY (Id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE AspNetRoles (
    Id               VARCHAR(255)   NOT NULL,
    Name             VARCHAR(256)   NULL,
    NormalizedName   VARCHAR(256)   NULL,
    ConcurrencyStamp TEXT           NULL,
    PRIMARY KEY (Id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE AspNetRoleClaims (
    Id         INT            NOT NULL AUTO_INCREMENT,
    RoleId     VARCHAR(255)   NOT NULL,
    ClaimType  TEXT           NULL,
    ClaimValue TEXT           NULL,
    PRIMARY KEY (Id),
    CONSTRAINT FK_AspNetRoleClaims_AspNetRoles_RoleId
        FOREIGN KEY (RoleId) REFERENCES AspNetRoles(Id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE AspNetUserClaims (
    Id         INT            NOT NULL AUTO_INCREMENT,
    UserId     VARCHAR(255)   NOT NULL,
    ClaimType  TEXT           NULL,
    ClaimValue TEXT           NULL,
    PRIMARY KEY (Id),
    CONSTRAINT FK_AspNetUserClaims_AspNetUsers_UserId
        FOREIGN KEY (UserId) REFERENCES AspNetUsers(Id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE AspNetUserLogins (
    LoginProvider       VARCHAR(255)  NOT NULL,
    ProviderKey         VARCHAR(255)  NOT NULL,
    ProviderDisplayName TEXT          NULL,
    UserId              VARCHAR(255)  NOT NULL,
    PRIMARY KEY (LoginProvider, ProviderKey),
    CONSTRAINT FK_AspNetUserLogins_AspNetUsers_UserId
        FOREIGN KEY (UserId) REFERENCES AspNetUsers(Id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE AspNetUserRoles (
    UserId VARCHAR(255) NOT NULL,
    RoleId VARCHAR(255) NOT NULL,
    PRIMARY KEY (UserId, RoleId),
    CONSTRAINT FK_AspNetUserRoles_AspNetRoles_RoleId
        FOREIGN KEY (RoleId) REFERENCES AspNetRoles(Id) ON DELETE CASCADE,
    CONSTRAINT FK_AspNetUserRoles_AspNetUsers_UserId
        FOREIGN KEY (UserId) REFERENCES AspNetUsers(Id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE AspNetUserTokens (
    UserId        VARCHAR(255) NOT NULL,
    LoginProvider VARCHAR(255) NOT NULL,
    Name          VARCHAR(255) NOT NULL,
    Value         TEXT         NULL,
    PRIMARY KEY (UserId, LoginProvider, Name),
    CONSTRAINT FK_AspNetUserTokens_AspNetUsers_UserId
        FOREIGN KEY (UserId) REFERENCES AspNetUsers(Id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ============================================================
-- 2. Application Tables
-- ============================================================

-- ParkingSlots (standalone, no FK)
CREATE TABLE ParkingSlots (
    SlotId     VARCHAR(10)  NOT NULL,
    IsOccupied TINYINT(1)   NOT NULL DEFAULT 0,
    GridX      INT          NOT NULL,
    GridY      INT          NOT NULL,
    PRIMARY KEY (SlotId)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Wallets (1:1 with AspNetUsers)
CREATE TABLE Wallets (
    Id      CHAR(36)       NOT NULL,
    Balance DECIMAL(18, 2) NOT NULL DEFAULT 0,
    UserId  VARCHAR(255)   NOT NULL,
    PRIMARY KEY (Id),
    CONSTRAINT FK_Wallets_AspNetUsers_UserId
        FOREIGN KEY (UserId) REFERENCES AspNetUsers(Id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- WalletTransactions (N:1 with Wallets)
CREATE TABLE WalletTransactions (
    Id        CHAR(36)       NOT NULL,
    Amount    DECIMAL(18, 2) NOT NULL,
    CreatedAt DATETIME       NOT NULL,
    Type      INT            NOT NULL,  -- 0 = TopUp, 1 = ParkingFee
    Status    INT            NOT NULL,  -- 0 = Pending, 1 = Completed, 2 = Failed
    OrderCode BIGINT         NOT NULL,
    WalletId  CHAR(36)       NOT NULL,
    PRIMARY KEY (Id),
    CONSTRAINT FK_WalletTransactions_Wallets_WalletId
        FOREIGN KEY (WalletId) REFERENCES Wallets(Id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- RetailReceipts (standalone)
CREATE TABLE RetailReceipts (
    ReceiptUid     VARCHAR(50)    NOT NULL,
    PurchaseAmount DECIMAL(18, 2) NOT NULL DEFAULT 0,
    IsClaimed      TINYINT(1)     NOT NULL DEFAULT 0,
    PRIMARY KEY (ReceiptUid)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ParkingSessions (N:1 with AspNetUsers, optional FK to RetailReceipts)
CREATE TABLE ParkingSessions (
    Id                 CHAR(36)       NOT NULL,
    LicensePlate       VARCHAR(20)    NOT NULL,
    EntryTime          DATETIME       NOT NULL,
    ExitTime           DATETIME       NULL,
    CalculatedFee      DECIMAL(18, 2) NULL,
    DiscountAmount     DECIMAL(18, 2) NOT NULL DEFAULT 0,
    Status             INT            NOT NULL,  -- 0 = Active, 1 = Paid, 2 = Completed
    UserId             VARCHAR(255)   NOT NULL,
    AppliedReceiptUid  VARCHAR(50)    NULL,
    PRIMARY KEY (Id),
    CONSTRAINT FK_ParkingSessions_AspNetUsers_UserId
        FOREIGN KEY (UserId) REFERENCES AspNetUsers(Id) ON DELETE CASCADE,
    CONSTRAINT FK_ParkingSessions_RetailReceipts_AppliedReceiptUid
        FOREIGN KEY (AppliedReceiptUid) REFERENCES RetailReceipts(ReceiptUid) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ============================================================
-- 3. Indexes
-- ============================================================

-- Identity indexes
CREATE INDEX IX_AspNetRoleClaims_RoleId   ON AspNetRoleClaims(RoleId);
CREATE INDEX IX_AspNetUserClaims_UserId   ON AspNetUserClaims(UserId);
CREATE INDEX IX_AspNetUserLogins_UserId   ON AspNetUserLogins(UserId);
CREATE INDEX IX_AspNetUserRoles_RoleId    ON AspNetUserRoles(RoleId);
CREATE INDEX EmailIndex                   ON AspNetUsers(NormalizedEmail(255));

CREATE UNIQUE INDEX RoleNameIndex         ON AspNetRoles(NormalizedName(256));
CREATE UNIQUE INDEX UserNameIndex         ON AspNetUsers(NormalizedUserName(256));

-- Application indexes
CREATE INDEX        IX_ParkingSessions_UserId              ON ParkingSessions(UserId);
CREATE INDEX        IX_ParkingSessions_AppliedReceiptUid   ON ParkingSessions(AppliedReceiptUid);
CREATE UNIQUE INDEX IX_Wallets_UserId                      ON Wallets(UserId);           -- enforces 1:1
CREATE INDEX        IX_WalletTransactions_OrderCode        ON WalletTransactions(OrderCode);
CREATE INDEX        IX_WalletTransactions_WalletId         ON WalletTransactions(WalletId);

SET FOREIGN_KEY_CHECKS = 1;

-- ============================================================
-- 4. Seed Data — 20 Parking Slots (5 columns x 4 rows)
-- ============================================================

INSERT INTO ParkingSlots (SlotId, GridX, GridY, IsOccupied)
VALUES
    ('A1', 1, 1, 0),
    ('A2', 2, 1, 0),
    ('A3', 3, 1, 0),
    ('A4', 4, 1, 0),
    ('A5', 5, 1, 0),
    ('B1', 1, 2, 0),
    ('B2', 2, 2, 0),
    ('B3', 3, 2, 0),
    ('B4', 4, 2, 0),
    ('B5', 5, 2, 0),
    ('C1', 1, 3, 0),
    ('C2', 2, 3, 0),
    ('C3', 3, 3, 0),
    ('C4', 4, 3, 0),
    ('C5', 5, 3, 0),
    ('D1', 1, 4, 0),
    ('D2', 2, 4, 0),
    ('D3', 3, 4, 0),
    ('D4', 4, 4, 0),
    ('D5', 5, 4, 0);
