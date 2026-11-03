package com.nebula.config;

import com.nebula.auth.UserAccount;
import com.nebula.auth.UserMapper;
import com.nebula.product.CatalogMapper;
import java.time.LocalDate;
import java.util.UUID;
import org.springframework.boot.ApplicationArguments;
import org.springframework.boot.ApplicationRunner;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Component;
import org.springframework.transaction.annotation.Transactional;

@Component
public class DemoDataInitializer implements ApplicationRunner {
    private final UserMapper users;
    private final CatalogMapper catalog;
    private final PasswordEncoder passwords;

    public DemoDataInitializer(UserMapper users, CatalogMapper catalog, PasswordEncoder passwords) {
        this.users = users;
        this.catalog = catalog;
        this.passwords = passwords;
    }

    @Override
    @Transactional
    public void run(ApplicationArguments args) {
        if (users.count() > 0) return;
        UUID userId = UUID.fromString("00000000-0000-0000-0000-000000000101");
        UUID supportId = UUID.fromString("00000000-0000-0000-0000-000000000102");
        UUID adminId = UUID.fromString("00000000-0000-0000-0000-000000000103");
        seedUser(userId, "demo@example.com", "demo@example.com", "演示用户", "USER", "demo-change-me");
        seedUser(supportId, "support@example.com", "support@example.com", "售后人员", "SUPPORT", "support-change-me");
        seedUser(adminId, "admin@example.com", "admin@example.com", "系统管理员", "ADMIN", "admin-change-me");

        UUID router = UUID.fromString("10000000-0000-0000-0000-000000000001");
        UUID camera = UUID.fromString("10000000-0000-0000-0000-000000000002");
        UUID x2 = UUID.fromString("20000000-0000-0000-0000-000000000001");
        UUID c1 = UUID.fromString("20000000-0000-0000-0000-000000000002");
        UUID x2fw = UUID.fromString("30000000-0000-0000-0000-000000000001");
        UUID c1fw = UUID.fromString("30000000-0000-0000-0000-000000000002");
        catalog.seedProduct(router, "ROUTER", "星云智家路由器", "network");
        catalog.seedProduct(camera, "CAMERA", "星云智家摄像头", "security");
        catalog.seedModel(x2, router, "X2", "X2 智能路由器");
        catalog.seedModel(c1, camera, "C1", "C1 智能摄像头");
        catalog.seedFirmware(x2fw, x2, "2.1.0", LocalDate.of(2026, 1, 15));
        catalog.seedFirmware(c1fw, c1, "1.4.0", LocalDate.of(2026, 2, 20));
        catalog.insertDevice(UUID.fromString("40000000-0000-0000-0000-000000000001"),
                "demo", userId, x2, x2fw, "DEMO-X2-0001", "客厅路由器");
    }

    private void seedUser(UUID id, String username, String email, String displayName,
                          String role, String password) {
        users.insert(new UserAccount(id, "demo", username, email, passwords.encode(password),
                displayName, "ACTIVE", role));
        users.insertRole(id, role);
    }
}
