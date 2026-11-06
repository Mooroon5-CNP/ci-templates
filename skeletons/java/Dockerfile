FROM maven:3.9-eclipse-temurin-21-alpine AS build
WORKDIR /src
COPY pom.xml ./
RUN mvn -q -B dependency:go-offline
COPY src/ ./src/
RUN mvn -q -B package -DskipTests

FROM eclipse-temurin:21-jre-alpine
WORKDIR /app
COPY --from=build /src/target/app.jar ./app.jar
USER 1000
EXPOSE {{APP_PORT}}
ENV PORT={{APP_PORT}}
HEALTHCHECK --interval=30s --timeout=5s CMD ["wget", "-qO-", "http://localhost:{{APP_PORT}}/healthz"]
CMD ["java", "-jar", "app.jar"]
