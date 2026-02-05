# SaaS Handbook

**Tags:** Curated Knowledge, DevOps, SaaS

## Abstract

A curated breakdown of the "Twelve-Factor App" for building scalable SaaS.

## Overview

I found this [great resource](https://12factor.net/) made by one of founder of Heroku, Adam Wiggins, which has been around since 2011. Their last commit was around 7 months ago (at the time I'm writing this, it's Feb 2026). Here, I elaborate on points that are often hard for beginners to digest. I have broken down the "Twelve Factors" into strictly technical explanations, stripping away confusing analogies. Since my primary languages are Python and Java, I have used them for all practical environment examples.

---

## 1. Codebase

More details: https://12factor.net/codebase. Following just key points that I think important (technically copy paste from the source, as they already said it best)

A codebase is any single repo, or any set of repos who share a root commit.

Always a one-to-one correlation between the codebase and the app.

- If there are multiple codebases, it’s not an app – it’s a distributed system. Each component in a distributed system is an app, and each can individually comply with 12-factor.

- Multiple apps sharing the same code is a violation of 12-factor. The solution here is to factor shared code into libraries which can be included through the dependency manager.

There is only one codebase per app, but there will be many deploys of the app. A deploy is a running instance of the app. This is typically a production site, and one or more staging sites. Additionally, every developer has a copy of the app running in their local development environment, each of which also qualifies as a deploy.

The codebase is the same across all deploys, although different versions may be active in each deploy. For example, a developer has some commits not yet deployed to staging; staging has some commits not yet deployed to production. But they all share the same codebase, thus making them identifiable as different deploys of the same app.

---

## 2. Dependencies

More details: https://12factor.net/dependencies

An app must function as a self-contained unit. It must strictly define exactly what external code it needs (Declaration) and strictly prevent the host OS's global libraries from interfering (Isolation).

Now, I find it useful to first make a distinction between Manifest and Artifact as I, myself, used to confuse between them.

### Manifest

The term "Manifest" comes from Latin meaning "clearly visible" or "to make public". In shipping, a "ship's manifest" is a document listing the cargo. In our context, it is a text file where us, developers, explicitly declares what the software needs. It is abstract constraints, not executable code.

**Mutability**: High as we edit this file frequently.

**Examples**:

- Java: `pom.xml` (Maven) or `build.gradle`
- Python: `requirements.txt` or `project.toml`

### Artifact

The term "Artifact" implies an object made by human skill or a process. It is a "fact" that has been created. In our case, artifact is the Binary Result. It is the concrete file generated or downloaded by the build tool based on the Manifest. It contains the bytecode the machine actually executes.

**Mutability**: Zero (Immutable). We do not edit an artifact; we replace it or rebuild it.

**Examples**:

- Java: compiled `.jar` (e.g., `gson-2.10.1.jar`) inside our `~/.m2/repository`
- Python: `.whl` or the installed folder inside `site-packages` (specific directory where Python installs libraries globally for the entire OS)

Also, Manifest is a small text file (KB). It is portable and lives in Git. It works on Windows, Linux, and Mac because it is just instructions. Artifact is a large binary file (MB/GB) and often platform-dependent.

### 2.1. Dependency Declaration

The app must possess a manifest file listing every library and version required. This guarantees determinism: if two developers build the project on different machines, the resulting artifacts must be identical.

In Python: Instead of manually installing libraries with `pip install`, we list them in a manifest file like `requirements.txt` or `project.toml`.

In Java: We do not manually download `.jar` files. We define them in a `pom.xml` (Maven) or `build.gradle` (Gradle).

The build system (Maven/Pip) reads this manifest to construct the "Dependency Graph", which resolves version conflicts and ensures the application has the exact bytecode it expects.

A typical build lifecycle is as follows:

- Input: Give the compiler the Manifest (Source Code).
- Output: The compiler produces an Artifact (Binary).
- In CI/CD (Continuous Integration/Deployment), this separation is absolute:
  - Developers commit Manifests.
  - Build Servers generate Artifacts.
  - Servers run Artifacts.

### 2.2. Dependency Isolation

Isolation ensures the application uses only the libraries defined in the manifest, strictly ignoring any libraries installed globally on the host OS.

**Python**:

- Violation: Running a script using the global /usr/bin/python. This interpreter interacts with the global `site-packages`, which may contain version conflicts.
- Correction: We must use a Virtual Environment (e.g., `venv`). This creates a localized directory containing a dedicated Python executable and library folder. When active, import statements resolve only to this folder.

**Java**:

- Violation: Relying on JARs present in the machine's global `CLASSPATH` environment variable.
- Correction: Modern build tools (Maven/Gradle) ignore the global `CLASSPATH`. They download dependencies into a local cache and construct a classpath explicitly for that specific execution context.

### 2.3. Avoiding "Shelling Out"

"Shelling out" means our code spawns a sub-process to execute a command-line tool installed on the OS (like `curl`, `grep`, etc.). This creates an Implicit Dependency. The code assumes the tool exists on the host OS, but it is not listed in the Manifest. If the server does not have `curl` installed, the app crashes.

Bad examples can be:

- Java

```java
Runtime.getRuntime().exec("curl http://example.com");
```

- Python

```python
os.system("curl http://example.com")
```

Instead of calling an external executable, we must declare a library in the Manifest that performs the same function. For example, we should add OkHttp (Java) or requests (Python) to the dependencies and use that library within the code logic.

---

## 3. Config

More details: https://12factor.net/config

This principle enforces a strict separation between Code (logic) and Configuration (environment-specific data). "Config" refers strictly to Operational Parameters. These are values that change depending on where the application is running (Deploy context).

- Config (Must be externalized): Database URLs, AWS Secret Keys, Redis ports, external API tokens
- Internal Application Data (Keep in code): Java Spring Bean definitions, Python URL routing tables, class structures. These do not change when moving from "Staging" to "Production"

**Litmus Test:**
If we can make our entire Git repository public on GitHub right now without leaking passwords or secret keys, our config is correctly separated. If we have to delete a file or edit a line before making it public, we have violated this principle.

**That's why we use environment variables**

These are key-value pairs maintained by the OS, accessible to the running process.

- Scope: They exist only in the memory of the running process, not in files.
- Agility: We can change a database URL by changing a deployment setting, without recompiling a JAR or editing a Python file.
- Language Agnostic: Every operating system (Linux, Windows) and every language (Java, Python) supports them natively.

Here is how we replace hardcoded constants with Environment Variables:

- Python:

```python
# BAD: Credentials are inside the code.
# If we commit this to Git, the secret is compromised.
class DatabaseConfig:
    URL = "postgres://user:password@prod-db.server.com:5432/mydb"

# Correction (Env Vars):
import os

# GOOD: The code asks the Operating System for the value.
# If the variable is missing, the app should fail fast (crash).
db_url = os.environ['DATABASE_URL']
```

- Java:

```java
// BAD: Reading from a file inside the JAR or classpath
Properties props = new Properties();
props.load(new FileInputStream("src/main/resources/config.properties"));
String dbUrl = props.getProperty("db.url");

// Correction (Env Vars):
// GOOD: Reading directly from the process environment
String dbUrl = System.getenv("DATABASE_URL");

if (dbUrl == null) {
    throw new RuntimeException("DATABASE_URL must be set");
}
```

### Grouping config into Environments (like development, test, production).

Problem: Frameworks often encourage creating files like `config/production.py` or `application-prod.yml`. This assumes that Prod is a single, static state.

- Say we need a Staging environment that is mostly like Production, but uses a different Email Service.
- Result: We have to copy production.py to staging.py and change one line. We now have duplicate config data. This causes a "combinatorial explosion" of config files.

Solution: Orthogonality (Independence)
Orthogonality means changing one variable does not affect others. We do not define "Environments"; we define "Variables"

Instead of saying "Load the Production Config," we simply set the variables for that specific deploy:

| Variable  | Staging Deploy     | Production Deploy | K's Dev Machine    |
| --------- | ------------------ | ----------------- | ------------------ |
| DB_HOST   | staging-db.aws.com | prod-db.aws.com   | localhost          |
| EMAIL_API | mock-email-service | sendgrid-live     | mock-email-service |
| CACHE_TTL | 60                 | 3600              | 1                  |

Each column is an independent collection of settings. We can mix and match these values infinitely without creating new config files in our source code.

---

## 4. Backing services

More details: https://12factor.net/backing-services

A backing service is any service the app consumes over the network as part of its normal operation. Backing services like database, caching, messaging/queueing, etc, are traditionally managed by the same systems administrators who deploy the app’s runtime. In addition to these locally-managed services, the app may also have services provided and managed by third parties. Examples include SMTP services (such as Postmark), metrics-gathering services (such as New Relic or Loggly), binary asset services (such as Amazon S3), and even API-accessible consumer services (such as Twitter, Google Maps, or Last.fm).

> no distinction between local and third party services

Both are attached resources, accessed via a URL or other locator/credentials stored in the config. A good app should be able to swap out a local MySQL database with one managed by a third party (such as Amazon RDS) without any changes to the app’s code.

Each distinct backing service is a resource. For example, a MySQL database is a resource; two MySQL databases (used for sharding at the application layer) qualify as two distinct resources. Resources can be attached to and detached from deploys at will.

**Example:** We have a Java app running in prod. It is currently connected to a primary database ("Database A").

Application Artifact: `myapp-v1.jar` (Immutable binary).

Configuration (Env Var): `DB_URL=jdbc:mysql://primary-db-host/users`

When the app starts, it reads `DB_URL` and opens a socket connection to `primary-db-host`.

Failure Event: The hard drive on `primary-db-host` corrupts. The database is slow or throwing I/O errors.

Administrator Action: The admin spins up a new database server ("Database B") and restores data from the last valid backup. "Database B" has a new IP address: `backup-db-host`.

The app is now connected to `backup-db-host`.

**Incorrect Way (Code Change):** If the developer had written "primary-db-host" inside the Java source code, they would have to:

- Edit code.
- Recompile `myapp-v1.jar`.
- Redeploy. This is too slow during an outage.

**Correct Way (Config Change):**

Admin updates the environment configuration of the running platform (e.g., Kubernetes ConfigMap or Heroku Config).

- Old Value: `DB_URL=jdbc:mysql://primary-db-host/users`
- New Value: `DB_URL=jdbc:mysql://backup-db-host/users`

Admin restarts the application process.

The exact same binary (`myapp-v1.jar`) starts up. It reads the environment variable again. This time, it sees the new address. It opens a socket to "Database B". The service is restored.

---

## 5. Build, release, run

More details: https://12factor.net/build-release-run

### 5.1. Build

> Code $\rightarrow$ Artifact

This is the transformation of source code into a static binary.

- **Input:** A specific commit from the Version Control System (Git) + The Dependency Manifest (`pom.xml` / `requirements.txt`).
- **Action:** The build server compiles the code and downloads (vendors) the specific libraries.
- **Output:** An **Artifact**. This is a bundle (like a `.jar` file or a Docker Image) that is agnostic to where it will run. It does not know if it is in "Test" or "Production".
- **Example:** Running `mvn package` to produce `myapp-1.0.jar`.

### 5.2. Release

> Artifact + Config $\rightarrow$ Execution Definition

This is the stage that combines the binary with the environment-specific settings.

- **Input:** The Artifact from the Build Stage + The Configuration (Environment Variables) for the target environment (e.g., Production database URLs, passwords).
- **Action:** The deployment system assigns a unique ID to this combination (e.g., "Release v100" or "2023-11-05_12-00").
- **Output:** A **Release**.

This stage acts as a "Save Point". Because we combined the binary and the config into a numbered release, we can easily reload this exact state later if we need to.

### 5.3. Run

> Release $\rightarrow$ Process

This is the actual execution of the application processes.

- **Input:** The specific Release selected by the administrator.
- **Action:** The Process Manager launches the app (e.g., `java -jar myapp-1.0.jar`).
- **Constraint:** This stage must be simple. It should not require compiling code or downloading files. It simply starts the process.

If the server crashes and reboots automatically at 3:00 AM, it must be able to restart without human intervention. If the "Run" stage relied on a complex build script, the restart might fail.

**Example:** We discover a critical bug in production. A line of code calculates tax incorrectly.

**Violation (Editing at Runtime)**

- **Action:** We SSH (log in remotely) into the production server. We open the file `tax_calculator.py` using `vim` or `nano` and correct the code directly on the running server.
- **Problem:**

1. **No Record:** The code in Git still has the bug. The code on the server has the fix. They are now out of sync.
2. **Loss of Fix:** Next week, when we deploy a new feature (Build/Release), the deployment tool overwrites our manual edit. The bug reappears ("Regression").
3. **Violation:** We changed the code during the **Run** stage.

**12-Factor Way**

- **Action:**

1. **Fix:** We fix the code on our local machine and commit to Git.
2. **Build:** The CI/CD pipeline compiles a new artifact (`v101`).
3. **Release:** The system combines `v101` with the production config.
4. **Run:** The system restarts the processes using the new Release `v101`.

**Result:** The fix is permanent, recorded in history, and reproducible.

Here are some important terms in the original webpage:

**Append-only Ledger**

- **Definition:** A record-keeping system where we can only add new entries, never delete or change old ones.
- **Context:** If Release v100 has a bug, we do not delete v100. We create Release v101. The history of v100 remains forever. This ensures we have a perfect history of what happened.

**Symlink (Symbolic Link)**

- **Definition:** A file system object that points to another directory. It is like a "Shortcut" in Windows. The page mentions Capistrano (a Ruby deployment tool) to explain **Rollbacks**.
- The server has a folder `current` which is a symlink pointing to `/releases/v100`.
- To roll back, we simply change the symlink to point to `/releases/v99`(instant, do not need to re-copy files; we just change where we point to)

---

## 6. Processes

> The app is executed in the execution environment as one or more processes.

Now, we know that a Process is a program that is currently running. When our code sits on the hard drive, it is just a file. When we execute it (e.g., `java -jar app.jar` or `python main.py`), the OS loads it into RAM and assigns it a unique ID (PID). This running instance is the Process. A process is temporary. It starts, it executes logic, and eventually, it crashes or stops.

"State" is simply Data that changes over time. It is the context of what has happened.

Stateful is when the process holds data in its own local RAM. For example: A user's login status, the items in a shopping cart, or a variable `counter = 0`. User A sends a request with `counter++`. Now `counter = 1`. Now, if the process crashes (restarts), RAM is wiped clean and `counter = 0` again. Also, if we have multiple processes, they cannot share data with each other. If we have two Processes running (Server 1 and Server 2), Server 2 cannot see the counter inside Server 1's RAM. They are isolated.

Stateless, as per the principle of 12-factor app, follows the [backing services principle](#4-backing-services). Now User A sends a request. The process connects to Redis, reads the value, increments it, and saves it back to Redis. If the process crashes, the data is safe in Redis. When the process restarts, it reads the correct value from Redis. If we have 100 processes running, they all read/write to the same Redis. They share the state perfectly without holding it themselves.

The 12-factor suggests Share-nothing principle. Process A implies nothing about Process B. They do not share files and they do not share RAM. We cannot simply write a file to a folder named `/temp/uploads` and expect it to be there 5 minutes later. In 5 minutes, our cloud provider might have killed that process and started a new one on a different physical machine. The new process will have a clean, empty `/temp` folder.

The author do mention using RAM is good only within the lifespan of one single request

**Example:**

- Request starts (User uploads a photo).
- Process saves photo to RAM.
- Process resizes photo.
- Process uploads photo to Amazon S3 (External Storage).
- Request ends. RAM is cleared.

As per this pattern, Sticky Session is deemed as pretty bad practice. Though, critically, I feel like that depends on the use case. Again, engineering is all about trade-offs. More insights on this topic can be found in [this article](https://www.geeksforgeeks.org/system-design/what-are-sticky-sessions-in-load-balancing/). Following is an example of when sticky session is bad.

Traditional webservers (like Tomcat or PHP) often store the user's Session (Login status) in the process's local RAM. To make this work with multiple servers, we can use Sticky Session, a Load Balancer configuration that forces User X to always connect to Server #1. Now, if Server #1 crashes, User X is logged out instantly, even if Server #2 is healthy. We cannot easily remove Server #1 to save money because it is "holding" active users.

A better approach would be to store the Session ID in a database (like Redis/Memcached) with a "Time-Expiration" (e.g., expire in 30 minutes). Every process checks Redis to see if the user is logged in.

---

## 7. Port Binding

> The app must be self-contained and not rely on a specific port number

More details: https://12factor.net/port-binding

Imagine our computer has 65,535 digital doors (16-bit integer ranging from 0 to 65,535). These are called Ports. Any data coming from the Internet must enter through one of these doors.

Our computer has one physical IP address (e.g., `192.168.1.5`) but runs many programs (Browser, Email, Spotify, Our App). When a data packet arrives at `192.168.1.5`, port number is how the Kernel know which program should receive it

- Port 80: The standard door for unencrypted Web Traffic (HTTP).
- Port 443: The standard door for encrypted Web Traffic (HTTPS).
- Port 3000/8080: Common "private" doors used by developers.

Now, there is this distinction between local computer and server that I feel like I should briefly mention here. Our local computer becomes a server the moment we run a program that opens a network port and waits for a connection. Again, they are both just "Execution Environments"

Now, as we define a server is a process that waits (normally does not initiate conversation). It binds to a port and enters an infinite loop, passively waiting for a "Client" (like a Browser) to connect and send data. It **serves** data back to the requester. Based on this definition, we can see that a webserver is a waiting process that speaks the web (HTTP on port 80) language. From this definition, we need a webserver because there is a **Language Gap** between our code and the Internet. Our code works with Objects and Variables and understands high-level concepts: `String message = "Hello";` or `return user_data;`. It does not natively understand how to manage network cables, electricity, or raw binary data streams.

The internet, on the other hand, transmits Raw Bytes (0s and 1s) over TCP/IP sockets. A network request looks like a stream of random characters arriving at the computer's port. Webserver (software) acts as the bridge between the raw network socket and our high-level code. It performs three critical technical tasks that our application logic should not have to handle:

**Socket Management (Connection)**

OS receives an electrical signal. The Webserver manages TCP Handshake to establish a connection. It holds the line open.

**Protocol Parsing (Translation)**

- Input: The webserver reads the raw stream of bytes: 47 45 54 20 2f 20 48...
- Processing: It parses (decodes) these bytes into a structured format that follows HTTP rules.
- Output: It creates a programming object (e.g., a `HttpServletRequest` object in Java or a `WSGI Environ` dictionary in Python) containing easy-to-read fields like `method="GET"` and `path="/home"`.
- Hand-off: Only now does it call function `my_code(request)`.

**Response Formatting (Packaging)**

- Input: The code returns a simple string: "Login Successful".
- Processing: We cannot just send that string. The browser expects HTTP headers (Status Codes, Content-Type, Content-Length).
- Action: The webserver automatically calculates the length (in bytes), adds the correct headers (e.g. `200 OK`), and converts everything back into a raw byte stream to send over the wire.

**Port Binding**

In traditional hosting (like PHP or early Java), the webserver is a separate, pre-installed master process. A system administrator installs Apache or Tomcat on the OS. This process runs permanently.

In deployment, we copy source code (the app) into a specific folder belonging to Apache (e.g., `/var/www/html`). Apache detects the files and executes code when a request comes in. The app is not self-contained. If we try to run the app on a machine without Apache installed, it does nothing. It has no way to "speak" to the network.

A proper principle would be the app must be **Self-Contained**. We do not install a global Webserver on the OS. We import a webserver library directly into our code (e.g., `import flask` in Python or `spring-boot-starter-web` in Java).

> We did not eliminate the Webserver; we moved its location. We shifted it from being a **Global Process** (installed on the OS) to being a **Library** (e.g., embedded inside our `.jar`).

This leads to the **Port Binding**.

**Container Injection (Traditional):** Application Server (Tomcat/Apache) binds

- Tomcat starts up.
- Tomcat calls `bind(80)`.
- Tomcat loads the code (e.g., `.war`).
- Our code never mentions a port. It just waits for Tomcat to call a method like `doGet()`

> no control over the network interface. It is passive.

```java
import javax.servlet.http.*;

public class MyServlet extends HttpServlet {
    // There is NO main() method here.
    // There is NO mention of Port 80 or 8080.

    @Override
    protected void doGet(HttpServletRequest req, HttpServletResponse resp) {
        // We only exist when Tomcat calls this method.
        resp.getWriter().write("Hello World");
    }
}
```

**Self-Contained (Modern):** Our code binds

- Our app starts (`java -jar app.jar`).
- Our app reads an Environment Variable (e.g., `PORT=5000`).
- Our app (via its internal library) calls `bind(5000)`.

> Our app actively claims the network interface. It "exports" its service by binding to that port

> Import Library $\rightarrow$ Run App $\rightarrow$ App Binds Port $\rightarrow$ App Receives Traffic

```java
// GOOD: Active, Self-contained
import org.springframework.boot.*;
import org.springframework.boot.autoconfigure.*;
import org.springframework.web.bind.annotation.*;

@RestController
@SpringBootApplication
public class MyApp {

    // 1. We define the endpoint logic
    @RequestMapping("/")
    String home() {
        return "Hello World";
    }

    // 2. We have a MAIN method
    public static void main(String[] args) {
        // 3. We read the PORT from the Environment
        // (Spring Boot does this automatically behind the scenes:
        // System.getenv("PORT"))

        // 4. We start the embedded web server (Tomcat/Jetty) internally
        // and bind to that port.
        SpringApplication.run(MyApp.class, args);
    }
}
```

Now, that is internal where our app listens on Port 5000. Yet, normal websites use Port 80 or 443. This is where the Load Balancer comes in. In production, a cloud Load Balancer (Routing Layer) sits in front of the app.

---

## 8. Concurrency

More details: https://12factor.net/concurrency

Concurrency is the ability of a system to execute multiple tasks or processes simultaneously. To achieve high scalability, modern applications utilize a process model where the workload is divided into independent execution units.

Traditionally, web applications have managed processes in two primary ways:

- On-Demand Child Processes: Used by languages like PHP. The webserver (Apache) starts a new child process (a subprocess created by a parent process) for incoming requests.
- Virtual Machine (VM) Model: Used by Java. JVM (Java Virtual Machine) starts one large uberprocess. It allocates a fixed block of Heap Memory (memory used for dynamic allocation) and CPU cycles immediately. Concurrency is handled internally via **Threads** (smaller units of execution within a single process that share the same memory space).

In 12-factor principles, processes are "first-class citizens", meaning they are the primary units of architecture.

Instead of one process doing everything, we define specific Process Types. This allows us to scale different parts of the application independently based on resource needs. You can actually witness this **logic** in Task Manager (while this is a client-side application, the logic directly mirrors the scale out via the process model)

- Web Process: Handles incoming HTTP requests and returns responses.
- Worker Process: Handles Asynchronous (not happening at the same time) background tasks, such as processing image uploads or sending emails.

![Microsoft Edge using Multi-Process](./images/concurrencyProcessTypeEdge.png)

**Horizontal Scaling**

While Vertical Scaling involves adding more CPU or RAM to a single machine, it has physical limits. The process model emphasizes Horizontal Scaling, where we add more identical processes across multiple physical or virtual machines.

12-factor processes must be Share-Nothing. Again, this means no process stores data (like session state or temporary files) on its local disk. All persistent data must be stored in a Backing Service (e.g., a database like PostgreSQL or a cache like Redis).

**Process Formation**

Process Formation is the total set of processes running the application.

Example: A formation might consist of 5 Web processes and 2 Worker processes. To handle a spike in traffic, we scale the formation to 10 Web processes without changing any code.

**External Process Management**

Processes should never Daemonize. [A daemon](#daemon) is a process that runs in the background and is not under the direct control of an interactive user. In this model, processes should not manage their own PID files (files containing the Process ID used by the OS to identify the instance).

Instead, we rely on an OS Process Manager (like systemd) or a Cloud Orchestrator (like Kubernetes). These managers handle:

- Output Streams: Capturing logs from stdout.
- Process Restart: Automatically restarting a process if it crashes (terminates unexpectedly).
- Lifecycle: Managing the startup and graceful shutdown of the application.

In Java, we can use Spring Boot to run our application as a process. While JVM uses threads for internal concurrency, the infrastructure treats the entire JVM as one process.

```java
// Internal Concurrency (Threading)
// JVM manages these threads inside one process
ExecutorService executor = Executors.newFixedThreadPool(10);
executor.submit(() -> {
    System.out.println("Processing task in a thread...");
});
```

To scale this according to the 12-factor principles, we do not increase the `ThreadPool` size (Vertical Scale). Instead, we run multiple instances of the compiled `.jar` file as separate OS processes (Horizontal Scale).

### Daemon

A Daemon (pronounced like "demon") is a computer program that runs as a background process rather than under the direct control of an interactive user. In the Unix Process Model, a daemon usually has the following characteristics:

- **No Controlling Terminal**: It is not attached to a keyboard or screen (stdin, stdout, and stderr are disconnected from the user interface).
- **Parent Process**: It is often a child of the init process (PID 1), which is the first process started by the kernel.
- **Naming Convention**: In Linux and Unix systems, daemon names usually end with the letter `d` (e.g., `sshd` for Secure Shell Daemon, `httpd` for HTTP Daemon).

In a server environment, many tasks must happen regardless of whether a user is logged in.

- **Handling Asynchronous Requests**: A web server needs to "listen" for traffic 24/7. A daemon like nginx or httpd stays active in the background to accept connections at any time.
- **Periodic Maintenance**: Systems need to perform cleanup. A daemon called crond (Cron Daemon) executes scheduled tasks, such as deleting temporary files or backing up a database at 2:00 AM.
- **Monitoring and Health**: OS use daemons to monitor hardware. For example, a daemon might monitor the CPU temperature and trigger a shutdown if it exceeds a certain Threshold (a specific limit or boundary).

In the past, developers wrote code to force the application into the background. This is called **Daemonizing**. This was done because in a Linux/Unix environment, every process we start is typically a "child" of our terminal shell (the window where we type commands). If we run a program (e.g., `python server.py`) and then close that terminal window, the OS detects the disconnection. The OS sends a specific signal called `SIGHUP`. The default behavior for a process receiving SIGHUP is to terminate immediately. (Signal Hang Up) to all processes attached to that terminal. Now, Developers wrote the "daemonize" code to strictly detach the application from the terminal. By daemonizig, when the terminal closes and sends `SIGHUP`, the detached application does not receive it and continues running.

Also, when we run a command in the foreground, it "blocks" the input.

- Foreground: We run `python server.py`. The cursor hangs. We cannot type any new commands in that shell until the server stops.
- Background: We want the server to run, but we also want to keep using our terminal to check files or run other commands.

By forcing the app into the background (forking), the process returns control of the terminal to the user immediately. The script returns an exit code of 0 (success) instantly to the shell, even though the actual application is still running in memory.

**Example: logging into a remote server to start a database**

Without Daemonization (Foreground):

1. We SSH into the server: `ssh user@server`.
2. We start the database: `./start_db`.
3. The database runs and prints logs to our screen.

Problem: We cannot disconnect. If we lose our internet connection or close our laptop, the SSH session breaks. The OS sends `SIGHUP`. The database dies.

With Daemonization (Background):

1. We SSH into the server.
2. We start the database: `./start_db`.
3. The code inside `./start_db` performs the `fork()` and detach logic.
4. The command finishes immediately and returns us to the prompt.
5. We disconnect from SSH.

Result: The database remains running on the server because it is no longer attached to our specific SSH user session.

### 12-Factor against making app daemonize itself

Now, forcing the app to background is a complicated task dealing with Linux kernel.

1. **fork()**: The process creates a copy of itself.
2. **Parent Exit**: The original process (parent) kills itself. The new process (child) is now "orphaned" and adopted by the OS init process. This detaches it from our terminal so it doesn't close when we close our window.
3. **setsid()**: It creates a new "session" so it is fully independent.
4. **PID File**: Because the original process died, the user doesn't know the ID of the new background process. The app must write its Process ID (PID) into a file (e.g., `/var/run/myapp.pid`) so the user can find it later to stop or restart it.

Here, If the app crashes before writing the PID file, the system loses track of it (Zombie process). Plus, this logic is specific to Linux/Unix. It might not work the same way on Windows or other environments.

The limitations with blocking and termination of being on foreground are back in the day given we relied purely on user shell. Now, we have Process Manager (like systemd, Docker, or Kubernetes), which make daemonizing (running in background) less ideal than foreground as per the 12-factor.

- Process Manager starts our application. It holds the parent position. Unlike a user shell, the Process Manager is designed to never close and never disconnect.
- When the 12-Factor app runs in the foreground, it is attached to the Process Manager's input/output streams, not our personal terminal.
  - Our Terminal: User $\rightarrow$ commands Process Manager
  - Background System: Process Manager $\rightarrow$ runs Application (Foreground)

Because the Process Manager runs in the background as a system service (a Daemon itself), it shields our "foreground" application from personal session disconnecting. With this, we have offload complex responsibilities from the messy Application Code to the Process Manager.

**Crash Detection (Exit Codes):**

- Background (Daemonized) App: If a daemon crashes silently, the OS might not notice immediately because the parent process already exited long ago (during `fork`). We need complex "PID watchers" to check if the process is still alive.
- Foreground App: If a foreground app crashes, the process terminates immediately. The Process Manager (its parent) sees the Exit Code (e.g., `Exit Code 1` for error) instantly. It can then automatically trigger a restart policy.

**Log Aggregation (Streams):**

- Background (Daemonized) App: The app must manage its own log files. It has to open `var/log/myapp`.log, handle file locks, and rotate files so they don't fill the disk.

- Foreground App: The app just `print()` to Standard Output (`stdout`). The Process Manager captures this stream and redirects it wherever we want (a file, a centralized logging server like Splunk, or a cloud dashboard) without the app needing to know.

**A good and common example is Docker.** When we run a Docker container:

- Inside the container, the application runs in the foreground (PID 1 inside the container a.k.a very first process started by the kernel).
- It prints logs to `stdout`.
- It blocks the "container's shell."

However, the Docker Engine (Process Manager) runs in the background on our server. It keeps that container alive, captures the logs, and restarts the container if the app crashes. The app thinks it is in the foreground, but the system treats it as a background service.

---

## 9. Disposability

More details: https://12factor.net/disposability

Disposability means that an application’s processes are ephemeral (temporary). They can be started or stopped immediately without causing errors or losing data.

This principle focuses on two technical goals:

- Fast Startup: The application starts quickly.
- Graceful Shutdown: The application stops safely when asked.

### 9.1. Fast Startup

A process should minimize the time between executing the launch command and being ready to accept traffic.

- **Elastic Scaling:** If traffic spikes and our autoscaler adds 10 new instances, they must be ready immediately. If startup takes 5 minutes, the traffic spike might overwhelm the system before the new instances are ready.
- **Recovery:** If a process crashes and the Process Manager restarts it, a slow startup means longer downtime.

**Example:**

- **Bad:** On startup, the application downloads a 5GB CSV file and parses it into HashMap memory. This takes 4 minutes. The app is "unhealthy" during this time.
- **Good:** The application connects to a Redis cache or Database where the data is already stored. Startup takes 5 seconds.

### 9.2. Graceful Shutdown (Web Process)

When the Process Manager (like Kubernetes) wants to stop a container, it sends a specific Linux signal called **`SIGTERM`** (Signal Terminate). The application must handle this signal to exit cleanly.

**The Sequence of Events:**

1. **Receive Signal:** The application detects `SIGTERM`.
2. **Stop Listening:** The web server stops accepting _new_ TCP connections on the service port (e.g., port 8080).
3. **Drain Requests:** The server allows _existing_ requests to finish processing.
4. **Exit:** Once active requests are done (or a timeout is reached), the process runs `System.exit(0)`.

**Example:**
Spring Boot has a setting `server.shutdown=graceful`.

- **Without it:** If we kill the app while a user is uploading a file, the upload fails (Connection Reset).
- **With it:** The server waits for the upload to finish before shutting down.

### 9.3. Graceful Shutdown (Worker Process)

Worker processes read jobs from a **Message Queue** (like RabbitMQ or Kafka). If they are shut down while processing a job, they must ensure the job is not lost.

**Mechanism: NACK (Negative Acknowledgement)**

- **Scenario:** A worker picks up a "Send Email" job. It receives `SIGTERM` halfway through generating the email.
- **Action:** The worker sends a **NACK** signal to the Queue.
- **Result:** The Queue puts the job back into the "Ready" list. Another worker picks it up and sends the email.

**Mechanism: Lock Release**

- **Scenario:** A system uses a Database table as a queue. The worker sets a flag `locked_by_worker_1 = true`.
- **Action:** On `SIGTERM`, the worker updates the row to set `locked_by_worker_1 = false`.
- **Result:** Other workers can now see and claim the job.

### 9.4. Robustness Against "Sudden Death"

Sometimes a process cannot shut down gracefully.

- **Hardware Failure:** The server power cord is pulled.
- **SIGKILL:** The Process Manager forces a kill (e.g., `kill -9`) because the process was stuck.

To handle this, operations must be **Reentrant** or **Idempotent**.

**Idempotency**
An operation is **Idempotent** if performing it multiple times produces the same result as performing it exactly once.

**Example of Non-Idempotent (Bad for Sudden Death):**

- **Code:** `UPDATE accounts SET balance = balance - 10 WHERE id = 1;`
- **Failure:** The worker decreases the balance, then crashes _before_ marking the job as "Done".
- **Restart:** The job is returned to the queue. A new worker runs the code again.
- **Result:** The user is charged $20 instead of $10.

**Example of Idempotent (Good for Sudden Death):**

- **Code:** `UPDATE accounts SET balance = 90 WHERE id = 1 AND transaction_id = 'abc';`
- **Failure:** The worker sets the balance to 90, then crashes.
- **Restart:** The new worker runs the _exact same SQL_. It sets the balance to 90 again.
- **Result:** The data remains correct ($10 deducted), no matter how many times the job runs.

This ensures that even if a worker dies instantly without cleaning up, the system recovers automatically when the job is retried.

---

## 10. Dev/prod parity

More details: https://12factor.net/dev-prod-parity

**Dev/Prod Parity** means keeping our **Development** environment (our local laptops) and our **Production** environment (the live servers) as identical as possible.

The goal is to eliminate the "It works on my machine" problem, where code passes tests locally but crashes when deployed to real users. Historically, development and production differed significantly. The 12-Factor methodology aims to close these gaps.

#### 10.1. The Time Gap

- **Traditional:** Developers work on a feature for weeks. They merge code once a month. This leads to massive, risky deployments ("Big Bang" releases).
- **12-Factor:** Developers practice **Continuous Deployment**. Code is committed, tested, and deployed to production hours or minutes after it is written.
- **Technical Benefit:** If a bug occurs, we know it was caused by the code written in the last hour, making debugging much faster.

#### 10.2. The Personnel Gap

- **Traditional:** Developers write code. They throw it "over the wall" to the Operations (Ops) team, who are responsible for deploying and maintaining it.
- **12-Factor:** Use a **DevOps** model. The developers who write the code are also involved in deploying and monitoring it.
- **Technical Benefit:** Developers write better code because they are the ones who get paged/woken up if the application crashes at night.

#### 10.3. The Tools Gap (Critical)

- **Traditional:** Developers use lightweight tools locally (e.g., macOS, SQLite, WEBrick) for speed. Production uses robust tools (e.g., Linux, PostgreSQL, Nginx) for stability.
- **12-Factor:** Use the **exact same** software stack and versions in both environments.

### 10.4. The Danger of Different Backing Services

A common mistake is using **SQLite** locally but **PostgreSQL** in production.

Developers often use libraries called **ORMs** (Object-Relational Mappers) like Hibernate (Java) or SQLAlchemy (Python). These libraries use **Adapters** to "abstract away" the database differences, allowing us to write Python/Java code instead of SQL.

**Why this fails:**
Even with an ORM, databases behave differently.

- **Scenario:** We have a table column named `Email`.
- **SQLite (Dev):** We search for `WHERE email = "User@Example.com"`. SQLite is often **case-insensitive** by default. It finds the record. The test passes.
- **PostgreSQL (Prod):** We run the same code. PostgreSQL is strictly **case-sensitive**. It cannot find the user. The login fails.
- **Result:** Production outage because of a configuration mismatch.

**Other Incompatibilities:**

- **Data Types:** SQLite acts differently with booleans or dates compared to MySQL.
- **Locking:** Production databases have complex row-level locking; lightweight local databases often lock the entire file, hiding concurrency bugs until production.
- **Features:** We cannot use advanced features like PostgreSQL's `JSONB` or `PostGIS` if our local environment doesn't support them.

### 10.5. Containerization

In the past, installing a heavy database like Oracle or PostgreSQL on a developer's laptop was difficult and slow. Today, we use **Docker** to solve the Tools Gap.

Instead of installing SQLite on our Mac/Windows, we run the **Production Database** in a container on our laptop.

**Example `docker-compose.yml` for Development:**

```yaml
services:
  web:
    build: .
    # Application runs here
  db:
    image: postgres:15.2-alpine # Exact version used in Production
    ports:
      - "5432:5432"
```

By doing this, our local environment is technically identical to the production cluster. If it works locally, it is mathematically highly probable to work in production.

| Gap           | Traditional (Bad)                 | 12-Factor (Good)                                 |
| ------------- | --------------------------------- | ------------------------------------------------ |
| **Time**      | Weeks/Months between deploys.     | Hours/Minutes (Continuous Deployment).           |
| **Personnel** | Devs write, Ops deploy (Silos).   | Devs deploy what they write (DevOps).            |
| **Tools**     | SQLite locally, Postgres in Prod. | Postgres locally, Postgres in Prod (via Docker). |

---

## 11. Logs

More details: https://12factor.net/logs

> Treat logs as event streams

In the 12-Factor, logging is not about writing text files to a hard drive. It is about generating a continuous stream of events that describes what the app is doing to stdout and stderr. and let the environment handle the rest.

### 11.1.No Log Files

Our app code should **never** try to write to a specific file (e.g., `/var/log/myapp.log`) or manage log rotation (creating new files when old ones get too big).

**Why:**

- **Statelessness:** 12-Factor apps are stateless. If you write logs to a local disk, those logs disappear if the container or server is destroyed.
- **Scalability:** If you have 50 instances of your app running on different servers, you cannot SSH into 50 different servers to read 50 different text files. You need them all in one place.
- **I/O Blocking:** Writing to a physical disk is slow. If the disk is full or busy, your application might crash or hang while trying to write a log line.

### 11.2. Solution: stdout

Instead of managing files, every running process writes its logs **unbuffered** to `stdout` (Standard Output) or `stderr` (Standard Error).

"Unbuffered" means the application pushes the text to the output stream immediately. It does not wait to accumulate a block of data in memory (a buffer) before sending it. This ensures that if the application crashes, the very last log line is preserved and not lost in RAM.

### 11.3. Log Aggregation Architecture

Since the app simply prints to `stdout`, the **Execution Environment** becomes responsible for capturing and storing the logs.

1. **Source:** The Application (PID 1) prints `{"timestamp": "...", "error": "DB connection failed"}` to `stdout`.
2. **Collector:** The Process Manager (Docker, Kubernetes, or Systemd) captures this stream.
3. **Router:** A specialized tool (like **Fluentd** or **Logstash**) reads the stream from the Collector.
4. **Destination:** The Router sends the logs to a centralized storage system (like **Splunk**, **Elasticsearch**, or **Datadog**).

This architecture completely decouples the **creation** of logs from the **storage** of logs. The developer can change the storage system (e.g., moving from Splunk to Datadog) without changing a single line of application code.

**Example (Python)**

**Bad Practice (Managing Files):**
The application creates a dependency on the file system.

```python
import logging

# BAD: Hardcoding a file path.
# This breaks if the app runs in a container with no write access to /var/log.
logging.basicConfig(filename='/var/log/myapp.log', level=logging.INFO)

def process_request():
    logging.info("Request received")

```

**Good Practice:**
The application writes to the console. The environment handles the rest.

```python
import logging
import sys

# GOOD: Writing to Standard Output (Stream)
# The 'stream=sys.stdout' argument directs logs to the console.
logging.basicConfig(stream=sys.stdout, level=logging.INFO)

def process_request():
    logging.info("Request received")

```

### 11.5. Why we need Centralized Analysis

Once the logs are aggregated into a system like Splunk or Elasticsearch, you can perform operations that are impossible with text files:

- **Time-Series Analysis:** "Show me the error rate over the last 24 hours."
- **Correlation:** "Show me all logs from the Web Service and the Database Service that happened at 10:00 AM."
- **Alerting:** "Trigger a PagerDuty alert if the phrase 'Out of Memory' appears more than 5 times in 1 minute".

---

## 12. Admin Processes

More details: https://12factor.net/admin-processes

### 12.1. "One-Off" vs. "Long-Running"

- **Long-Running Processes:** These run indefinitely to serve traffic (e.g., Web Server, Worker). They are managed by the Process Manager (start, restart on crash).
- **One-Off Processes:** These run once to perform a specific task and then terminate (exit) immediately.

### 12.2. Golden Rule: Identical Environment

The most critical technical requirement is that admin processes must run in the **exact same environment** as the application.

- **Same Release:** They must run against the exact version of the code that is currently deployed.
- **Same Config:** They must load the exact same Environment Variables (DB URL, API Keys) as the web process.
- **Same Dependencies:** They must use the exact same libraries and binaries.

**Why:** If a developer runs a database migration script from their laptop (Local Environment) connecting to the Production Database:

1. **Dependency Mismatch:** The laptop might have `SQLAlchemy version 2.0` while production uses `1.4`. This could generate invalid SQL syntax and corrupt the production database.
2. **Network Security:** Production databases should be isolated inside a private VPC (Virtual Private Cloud). Allowing direct access from a laptop requires opening firewalls, which creates a security vulnerability.

### 12.3. Common Admin Process Types

#### Database Migrations

**Technical Definition:** A script that alters the database schema (structure).

- **Example:** Adding a `phone_number` column to the `Users` table.
- **Command:** `python manage.py migrate` (Django) or `npm run db:migrate` (Node.js).
- **12-Factor Execution:** This command is executed inside a container/process that has the strict code and config of the current release.

#### REPL (Read-Eval-Print Loop)

An interactive shell that allows you to execute code dynamically against the live application context.

- **Usage:** We use this to inspect data or debug logic using live production models without writing a new script.
- **Example (Python):**

```bash
$ python manage.py shell
>>> from myapp.models import User
>>> User.objects.filter(is_active=False).count()
42

```

### 12.4. Docker Example

Now, SSH to log into a server to run these scripts is not a good practice as that changes the server state. Instead, we use the container runtime.

**Scenario:** We need to run a migration on our running app.

**Bad (Violates Dependency Isolation):**
Running the script from your local machine.

```bash
# Executed on Developer Laptop
# DANGER: Uses local Python version and local env vars
python manage.py migrate

```

**Good:**
Using the container that is already built for production.

```bash
# Executed via Docker CLI
# 1. 'run': Create a new one-off process.
# 2. '--rm': Remove the container immediately after it finishes (Disposable).
# 3. 'myapp:latest': Use the EXACT image deployed in production.
# 4. 'python manage.py migrate': The specific admin command.

docker run --rm --env-file .env myapp:latest python manage.py migrate

```

This guarantees that the migration runs with the exact same `python` binary and library versions as your web server.

---

## Summary of Twelve Factors

1. **Codebase:** One repo, tracked in Git.
2. **Dependencies:** Explicitly declared (pip/npm), no system-wide packages.
3. **Config:** Stored in Environment Variables, not code.
4. **Backing Services:** Treated as attached resources (URL connection strings).
5. **Build, Release, Run:** Strict separation of stages.
6. **Processes:** Stateless, share-nothing, horizontal scaling.
7. **Port Binding:** App exports HTTP, not dependent on web server injection.
8. **Concurrency:** Scale out via process types (Web/Worker).
9. **Disposability:** Fast startup, graceful shutdown.
10. **Dev/Prod Parity:** Keep environments identical (Docker).
11. **Logs:** Stream to `stdout`, aggregated by the environment.
12. **Admin Processes:** One-off tasks run in the production environment context.
