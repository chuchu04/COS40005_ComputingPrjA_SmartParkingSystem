using Microsoft.AspNetCore.Identity.EntityFrameworkCore;
using Microsoft.EntityFrameworkCore;
using WebApplication1.Models;

namespace WebApplication1.Data
{
    public class ApplicationDbContext : IdentityDbContext<ApplicationUser>
    {
        public ApplicationDbContext(DbContextOptions<ApplicationDbContext> options)
            : base(options)
        {
        }

        public DbSet<Wallet> Wallets => Set<Wallet>();
        public DbSet<WalletTransaction> WalletTransactions => Set<WalletTransaction>();
        public DbSet<ParkingSlot> ParkingSlots => Set<ParkingSlot>();
        public DbSet<ParkingSession> ParkingSessions => Set<ParkingSession>();
        public DbSet<RetailReceipt> RetailReceipts => Set<RetailReceipt>();

        protected override void OnModelCreating(ModelBuilder builder)
        {
            base.OnModelCreating(builder);

            // 1-to-1: ApplicationUser <-> Wallet
            builder.Entity<ApplicationUser>()
                .HasOne(u => u.Wallet)
                .WithOne(w => w.User)
                .HasForeignKey<Wallet>(w => w.UserId)
                .OnDelete(DeleteBehavior.Cascade);

            // 1-to-many: Wallet -> WalletTransactions
            builder.Entity<Wallet>()
                .HasMany(w => w.WalletTransactions)
                .WithOne(t => t.Wallet)
                .HasForeignKey(t => t.WalletId)
                .OnDelete(DeleteBehavior.Cascade);

            // 1-to-many: ApplicationUser -> ParkingSessions
            builder.Entity<ApplicationUser>()
                .HasMany(u => u.ParkingSessions)
                .WithOne(s => s.User)
                .HasForeignKey(s => s.UserId)
                .OnDelete(DeleteBehavior.Cascade);

            // Optional many-to-1: ParkingSession -> RetailReceipt
            builder.Entity<ParkingSession>()
                .HasOne(s => s.AppliedReceipt)
                .WithMany(r => r.ParkingSessions)
                .HasForeignKey(s => s.AppliedReceiptUid)
                .OnDelete(DeleteBehavior.SetNull);

            // Index on OrderCode for fast PayOS webhook lookups
            builder.Entity<WalletTransaction>()
                .HasIndex(t => t.OrderCode);

            // Seed 20 ParkingSlots in a 5-column x 4-row grid
            var slots = new List<ParkingSlot>();
            char[] rows = { 'A', 'B', 'C', 'D' };

            for (int y = 0; y < rows.Length; y++)       // 4 rows
            {
                for (int x = 0; x < 5; x++)             // 5 columns
                {
                    slots.Add(new ParkingSlot
                    {
                        SlotId = $"{rows[y]}{x + 1}",   // A1..A5, B1..B5, C1..C5, D1..D5
                        IsOccupied = false,
                        GridX = x + 1,                   // 1-based
                        GridY = y + 1
                    });
                }
            }

            builder.Entity<ParkingSlot>().HasData(slots);
        }
    }
}
