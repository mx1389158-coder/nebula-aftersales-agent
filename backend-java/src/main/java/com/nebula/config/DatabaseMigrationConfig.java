package com.nebula.config;

import javax.sql.DataSource;
import org.flywaydb.core.Flyway;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

/** Makes the business schema migration order explicit on Spring Boot 4. */
@Configuration
public class DatabaseMigrationConfig {
    @Bean(initMethod = "migrate")
    Flyway businessFlyway(DataSource dataSource) {
        return Flyway.configure()
                .dataSource(dataSource)
                .createSchemas(true)
                .defaultSchema("biz")
                .schemas("biz")
                .locations("classpath:db/migration")
                .load();
    }
}
