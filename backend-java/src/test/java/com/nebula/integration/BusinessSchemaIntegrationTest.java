package com.nebula.integration;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.ResultSet;
import java.sql.Statement;
import org.flywaydb.core.Flyway;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;
import org.testcontainers.containers.PostgreSQLContainer;
import org.testcontainers.junit.jupiter.Container;
import org.testcontainers.junit.jupiter.Testcontainers;

@Testcontainers(disabledWithoutDocker = true)
class BusinessSchemaIntegrationTest {
    @Container
    static final PostgreSQLContainer<?> POSTGRES = new PostgreSQLContainer<>("postgres:16-alpine")
            .withDatabaseName("aftersales").withUsername("test").withPassword("test");

    @BeforeAll
    static void migrate() {
        Flyway.configure().dataSource(POSTGRES.getJdbcUrl(), POSTGRES.getUsername(),
                        POSTGRES.getPassword()).createSchemas(true).defaultSchema("biz")
                .schemas("biz").locations("classpath:db/migration").load().migrate();
    }

    @Test
    void migrationsCreateAgentContextAndTraceColumns() throws Exception {
        try (Connection connection = connection(); Statement statement = connection.createStatement()) {
            ResultSet result = statement.executeQuery("""
                    SELECT count(*) FROM information_schema.columns
                    WHERE table_schema='biz' AND
                    ((table_name='tickets' AND column_name='agent_context') OR
                     (table_name='audit_logs' AND column_name='trace_id'))
                    """);
            result.next();
            assertThat(result.getInt(1)).isEqualTo(2);
        }
    }

    @Test
    void databaseRejectsInvalidUserStatus() throws Exception {
        try (Connection connection = connection(); Statement statement = connection.createStatement()) {
            assertThatThrownBy(() -> statement.executeUpdate("""
                    INSERT INTO biz.users(id, tenant_id, username, email, password_hash,
                      display_name, status)
                    VALUES('00000000-0000-0000-0000-000000000901', 'demo', 'invalid',
                      'invalid@example.com', 'hash', 'invalid', 'UNKNOWN')
                    """)).isInstanceOf(Exception.class);
        }
    }

    private static Connection connection() throws Exception {
        return DriverManager.getConnection(POSTGRES.getJdbcUrl(), POSTGRES.getUsername(),
                POSTGRES.getPassword());
    }
}
