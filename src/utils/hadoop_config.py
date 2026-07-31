import os
import sys

WINDOWS_HADOOP_HOME = r"C:\hadoop"


def configure_windows_hadoop() -> None:
    """Configura variaveis necessarias para Spark no Windows (winutils)."""
    if os.name != "nt":
        return

    hadoop_home = os.environ.get("HADOOP_HOME") or WINDOWS_HADOOP_HOME
    winutils_path = os.path.join(hadoop_home, "bin", "winutils.exe")

    if not os.path.exists(winutils_path):
        raise RuntimeError(
            "winutils.exe nao encontrado. Configure HADOOP_HOME corretamente ou instale em C:\\hadoop\\bin\\winutils.exe"
        )

    os.environ["HADOOP_HOME"] = hadoop_home
    os.environ["hadoop.home.dir"] = hadoop_home
    os.environ["PATH"] = (
        os.path.join(hadoop_home, "bin") + os.pathsep + os.environ.get("PATH", "")
    )

    # Em Windows, garante que driver/executor usem o mesmo Python do ambiente ativo.
    os.environ["PYSPARK_PYTHON"] = sys.executable
    os.environ["PYSPARK_DRIVER_PYTHON"] = sys.executable
