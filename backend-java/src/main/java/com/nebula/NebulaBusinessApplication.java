package com.nebula;

import com.nebula.security.SecurityProperties;
import org.mybatis.spring.annotation.MapperScan;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.cache.annotation.EnableCaching;

@SpringBootApplication
@EnableCaching
@MapperScan("com.nebula")
@EnableConfigurationProperties(SecurityProperties.class)
public class NebulaBusinessApplication {
    public static void main(String[] args) {
        SpringApplication.run(NebulaBusinessApplication.class, args);
    }
}
