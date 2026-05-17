# SIA-Projects LangChain CLI - DEPENDENCY INSTALLATION

## Install Dependencies

Run this command in a PowerShell Terminal:

```shell
pip install -r requirements-dev.txt
```

After this, please install the software programs mentioned in the next section.

### Dependency List

```shell
colorama>=0.4.6
langchain-core>=1.0.2
langchain-neo4j>=0.6.0
langchain-ollama>=1.0.0
neo4j>=5.28.2
ollama>=0.6.0
python-dotenv>=1.2.1
textwrap3>=0.9.2
```

These are the dependencies required by the application at the time of its submission: `November 2025`.

Check your installed dependencies by running the following command in PowerShell (search for an equivalent if you are using Linux/Mac):

```shell
pip list | Select-String "langchain|ollama|neo4j|dotenv|colorama|textwrap"
```

## Required Software

There are two software applications **you must always run** in parallel to the [cli.py](sia_projects_langchain/sia_projects/cli.py) program:

- Neo4J Desktop
- Ollama Server (with an Ollama 3.1 8b Model)

### Neo4J Desktop

Visit this website and download the **desktop** application:

<https://neo4j.com/download/>

Create a new instance under `Local Instances` and use the default parameters. You may use a simple database password such as "password".

![Neo4j instance](/images/image.png)

You can start the database at any time by clicking on the "Start Instance" button.

![Start instance](/images/image-1.png)


#### APOC PLUGIN

You need this plugin to properly traverse the langchain.

![APOC plugin](/images/image-3.png)

Click on the three buttons on the right side of the instance and install the plugin called:

```shell
APOC
```

**You must keep the the local database instance running in the background while using the CLI.**

### Ollama Server

Visit this website and download the desktop application:

<https://ollama.com/download/linux>

After installing the Ollama application, open a terminal (PowerShell on Windows, Terminal on Mac/Linux) and run:

```shell
ollama pull llama3.1:8b
```

This downloads the Llama 3.1 8-billion-parameter model, which is required by the SIA-Projects CLI.

You can verify the installation by running:

```shell
ollama list
```

If installed, you will see something like:

```shell
NAME            SIZE
llama3.1:8b     4.9GB
```

**You must keep the Ollama server running in the background while using the CLI.**

By running the Ollama desktop application, you will automatically start a background server.  

If it is not running, start it manually with:

```shell
ollama serve
```
