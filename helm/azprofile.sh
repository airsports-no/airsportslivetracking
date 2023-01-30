# mkdir -p ~/az-profiles/{airsports,test,devops,local}
# place in .bashrc: . /mnt/c/Users/xa36/Documents/azprofile.sh
# az login
# az aks get-credentials --resource-group airsports_group --name airsports
# az aks get-credentials --resource-group XA-Test-rg --name XA-Test-AKS
# az acr login --name airsportsacr
# \[\e]0;\u@\h: \w\a\]${debian_chroot:+($debian_chroot)}\[\033[01;32m\]\u@\h\[\033[00m\]:\[\033[01;34m\]\w\[\033[00m\]\$
# export PS1='\[\e]0;\u@\h: \w\a\]${debian_chroot:+($debian_chroot)}\[\033[01;32m\]\u@[az|$CURRENT_AZURE_CONFIG]\[\033[00m\]:\[\033[01;34m\]\W\[\033[00m\]\$'
# curl -LO https://storage.googleapis.com/minikube/releases/latest/minikube-linux-amd64
# sudo install minikube-linux-amd64 /usr/local/bin/minikube
# Remember to switch to local profile first
# minikube start


export AZURE_CONFIG_DIR=~/az-profiles/airsports
export KUBECONFIG=~/az-profiles/airsports/kubeconfig.yaml
export CURRENT_AZURE_CONFIG=airsports
 
function azprofile {
    AIRSPORTSPATH=~/az-profiles/airsports  # az aks get-credentials --resource-group airsports_group --name airsports && az acr login --name airsportsacr
    TESTPATH=~/az-profiles/test  # az aks get-credentials --resource-group XA-Test-rg --name XA-Test-AKS && az acr login --name spncreg
	DEVOPSPATH=~/az-profiles/devops
	LOCALPATH=~/az-profiles/local


    ERRORMSG="Invalid usage. Usage: azprofile [show|set] [airsports|test|devops|local|default]"
    
    CMD=${1:?"$ERRORMSG"}
    
    if [ "$CMD" = "show" ]; then
        if [ -z "$AZURE_CONFIG_DIR" ]; then
            echo "The current az-cli config dir: ~/.azure"
        else
            echo "The current az-cli config dir: $AZURE_CONFIG_DIR"
        fi
        if [ -z "$KUBECONFIG" ]; then
            echo "The current kubectl config dir: ~/.kube"
        else
            echo "The current kubectl config dir: $KUBECONFIG"
        fi
    elif [ $CMD = "set" ]; then
        AZENV=${2:?"$ERRORMSG"}
        if [ $AZENV = "airsports" ]; then
            export AZURE_CONFIG_DIR=$AIRSPORTSPATH
            export KUBECONFIG=$AIRSPORTSPATH/kubeconfig.yaml
			export CURRENT_AZURE_CONFIG=$AZENV
			# az acr login --name airsportsacr
            echo "Azure config directory has been set to $AIRSPORTSPATH"
        elif [ $AZENV = "test" ]; then
            export AZURE_CONFIG_DIR=$TESTPATH
            export KUBECONFIG=$TESTPATH/kubeconfig.yaml
			export CURRENT_AZURE_CONFIG=$AZENV
			# az acr login --name spncreg
			# az aks get-credentials --resource-group "XA-Test-rg" --name XA-Test-AKS
            echo "Azure config directory has been set to $TESTPATH"
        elif [ $AZENV = "devops" ]; then
            export AZURE_CONFIG_DIR=$DEVOPSPATH
            export KUBECONFIG=$DEVOPSPATH/kubeconfig.yaml
			export CURRENT_AZURE_CONFIG=$AZENV
			# az acr login --name spncreg
            echo "Azure config directory has been set to $DEVOPSPATH"
        elif [ $AZENV = "local" ]; then
            export AZURE_CONFIG_DIR=$LOCALPATH
            export KUBECONFIG=$LOCALPATH/kubeconfig.yaml
			export CURRENT_AZURE_CONFIG=$AZENV
			# az acr login --name airsportsacr
            echo "Azure config directory has been set to $LOCALPATH"
        elif [ $AZENV = "default" ]; then
            unset AZURE_CONFIG_DIR
            unset KUBECONFIG
			export CURRENT_AZURE_CONFIG=airsports
			# az acr login --name airsportsacr
            echo "Azure config directory has been set to default directory"
        else
            echo "$ERRORMSG"
        fi
    else
        echo "$ERRORMSG"
    fi
}