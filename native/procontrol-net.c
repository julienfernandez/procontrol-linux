/* SPDX-License-Identifier: GPL-3.0-or-later
 * Open two ProControl Ethernet sockets and pass them to the calling user.
 * No commands executed, no files opened, no UID changes. CAP_NET_RAW only.
 */
#define _GNU_SOURCE
#include <sys/socket.h>
#include <net/if.h>
#include <linux/if_packet.h>
#include <arpa/inet.h>
#include <unistd.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <errno.h>
static int fail(const char *what) { perror(what); return 1; }
int main(int argc, char **argv) {
    if(argc != 3 || strcmp(argv[1], "enp0s25")) {
        fprintf(stderr,"Usage: procontrol-net enp0s25 inherited-unix-fd\n"); return 2;
    }
    char *end; errno=0; long value=strtol(argv[2],&end,10);
    if(errno || !*argv[2] || *end || value<3 || value>1048576) return 2;
    int channel=(int)value, domain=0,type=0; socklen_t size=sizeof(int);
    if(getsockopt(channel,SOL_SOCKET,SO_DOMAIN,&domain,&size) || domain!=AF_UNIX) return 2;
    size=sizeof(int);
    if(getsockopt(channel,SOL_SOCKET,SO_TYPE,&type,&size) || type!=SOCK_SEQPACKET) return 2;
    unsigned index=if_nametoindex(argv[1]); if(!index) return fail("Ethernet interface");
    int fd[2]={-1,-1};
    struct sockaddr_ll addr={.sll_family=AF_PACKET,.sll_protocol=htons(0x885f),.sll_ifindex=(int)index};
    for(int i=0;i<2;i++) {
        fd[i]=socket(AF_PACKET,SOCK_RAW|SOCK_CLOEXEC,htons(0x885f));
        if(fd[i]<0) return fail("CAP_NET_RAW required");
        if(bind(fd[i],(struct sockaddr*)&addr,sizeof(addr))) return fail("Ethernet bind");
    }
    int buffer=4*1024*1024;setsockopt(fd[0],SOL_SOCKET,SO_RCVBUF,&buffer,sizeof(buffer));
    char byte='P';struct iovec io={.iov_base=&byte,.iov_len=1};
    union {struct cmsghdr align; char bytes[CMSG_SPACE(sizeof(fd))];} control={0};
    struct msghdr msg={.msg_iov=&io,.msg_iovlen=1,.msg_control=control.bytes,.msg_controllen=sizeof(control)};
    struct cmsghdr *c=CMSG_FIRSTHDR(&msg); c->cmsg_level=SOL_SOCKET;c->cmsg_type=SCM_RIGHTS;c->cmsg_len=CMSG_LEN(sizeof(fd));
    memcpy(CMSG_DATA(c),fd,sizeof(fd));
    if(sendmsg(channel,&msg,MSG_NOSIGNAL)!=1)return fail("Pass Ethernet sockets");
    close(fd[0]);close(fd[1]);return 0;
}
